"""Authenticated owner dashboard API for the Vercel frontend.

The dashboard is a convenience surface over the same deterministic domain
service. It never exposes planning data without the dashboard bearer token and
it never lets the browser write task status without an explicit owner action.
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import func, select

from zasky.domain.errors import DomainError
from zasky.domain.schemas import CompleteTaskRequest
from zasky.planner.core import as_utc
from zasky.storage.models import (
    AuditEvent,
    DayPlan,
    DayPlanItem,
    FixedEvent,
    MonthCommitment,
    WeekPlacement,
    WeekTask,
)

if TYPE_CHECKING:
    from zasky.app import ZaskyApp


class CompleteTaskBody(BaseModel):
    actual_min: int | None = Field(default=None, ge=0, le=100000)


def _secret_value(value: SecretStr | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        return value.get_secret_value().strip()
    return str(value).strip()


def _time_label(value: datetime | None, tz: ZoneInfo) -> str | None:
    if value is None:
        return None
    return as_utc(value).astimezone(tz).strftime("%I:%M %p").lstrip("0")


def _day_bounds(local_date: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(local_date, time.min, tzinfo=tz).astimezone(UTC)
    end = datetime.combine(
        local_date + timedelta(days=1), time.min, tzinfo=tz
    ).astimezone(UTC)
    return start, end


def _task_payload(
    task: WeekTask,
    *,
    week_start: date | None = None,
    commitment_title: str | None = None,
) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "est_min": task.est_min,
        "actual_min": task.actual_min,
        "scheduled_date": task.scheduled_date.isoformat(),
        "status": task.status,
        "ad_hoc": task.ad_hoc,
        "resume_note_present": bool(task.resume_note),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "week_start": week_start.isoformat() if week_start else None,
        "commitment_title": commitment_title,
    }


def create_dashboard_app(app: ZaskyApp) -> FastAPI:
    """Build the public-but-token-gated dashboard API."""

    settings = app.settings
    dashboard = FastAPI(
        title="Zasky owner dashboard API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    origins = [
        item.strip()
        for item in settings.dashboard_cors_origins.split(",")
        if item.strip()
    ] or ["*"]
    dashboard.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    async def require_token(
        authorization: str | None = Header(default=None),
    ) -> None:
        configured = _secret_value(settings.dashboard_api_key)
        if not configured:
            raise HTTPException(
                status_code=503,
                detail="Dashboard API is not configured.",
            )
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=401,
                detail="Missing dashboard bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not secrets.compare_digest(token.strip(), configured):
            raise HTTPException(
                status_code=401,
                detail="Invalid dashboard bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def local_today() -> date:
        return datetime.now(UTC).astimezone(ZoneInfo(settings.timezone)).date()

    @dashboard.get("/api/dashboard/today", dependencies=[Depends(require_token)])
    async def today(
        local_date: date | None = Query(default=None, alias="date"),
    ) -> dict[str, Any]:
        target = local_date or local_today()
        tz = ZoneInfo(settings.timezone)
        start_utc, end_utc = _day_bounds(target, tz)
        async with app.db.locked_session() as session:
            plan = await session.scalar(
                select(DayPlan)
                .where(
                    DayPlan.local_date == target,
                    DayPlan.status == "approved",
                )
                .order_by(DayPlan.revision.desc())
                .limit(1)
            )
            events = (
                await session.execute(
                    select(FixedEvent)
                    .where(FixedEvent.status == "active")
                    .order_by(FixedEvent.starts_at_utc)
                )
            ).scalars().all()
            fixed = [
                {
                    "id": event.id,
                    "title": event.title,
                    "starts_at_utc": event.starts_at_utc.isoformat(),
                    "ends_at_utc": event.ends_at_utc.isoformat(),
                    "starts_at_display": _time_label(event.starts_at_utc, tz),
                    "ends_at_display": _time_label(event.ends_at_utc, tz),
                }
                for event in events
                if as_utc(event.starts_at_utc) < end_utc
                and as_utc(event.ends_at_utc) > start_utc
            ]
            payload: dict[str, Any] = {
                "date": target.isoformat(),
                "timezone": settings.timezone,
                "has_plan": plan is not None,
                "battery": None,
                "source": None,
                "latest_wake_utc": None,
                "latest_wake_display": None,
                "must": [],
                "should": [],
                "fixed_events": fixed,
            }
            if plan is None:
                return payload

            rows = (
                await session.execute(
                    select(DayPlanItem, WeekTask)
                    .join(WeekTask, DayPlanItem.task_id == WeekTask.id)
                    .where(DayPlanItem.day_plan_id == plan.id)
                    .order_by(DayPlanItem.position)
                )
            ).all()
            payload.update(
                {
                    "battery": plan.battery,
                    "source": plan.source,
                    "latest_wake_utc": (
                        plan.latest_wake_utc.isoformat()
                        if plan.latest_wake_utc
                        else None
                    ),
                    "latest_wake_display": _time_label(plan.latest_wake_utc, tz),
                }
            )
            for item, task in rows:
                entry = {
                    **_task_payload(task),
                    "disposition": item.disposition,
                    "position": item.position,
                    "outcome": item.outcome,
                    "planned_est_min": item.planned_est_min,
                    "planned_start_utc": (
                        item.planned_start_utc.isoformat()
                        if item.planned_start_utc
                        else None
                    ),
                    "planned_end_utc": (
                        item.planned_end_utc.isoformat()
                        if item.planned_end_utc
                        else None
                    ),
                    "planned_start_display": _time_label(
                        item.planned_start_utc, tz
                    ),
                    "planned_end_display": _time_label(item.planned_end_utc, tz),
                }
                key = "must" if item.disposition == "must" else "should"
                payload[key].append(entry)
            return payload

    @dashboard.get("/api/dashboard/tasks", dependencies=[Depends(require_token)])
    async def tasks(
        status: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        allowed = {"active", "parked", "completed", "cancelled"}
        if status is not None and status not in allowed:
            raise HTTPException(status_code=400, detail="Unknown task status.")
        async with app.db.locked_session() as session:
            statement = (
                select(WeekTask, WeekPlacement, MonthCommitment)
                .join(WeekPlacement, WeekTask.placement_id == WeekPlacement.id)
                .outerjoin(
                    MonthCommitment,
                    WeekPlacement.commitment_id == MonthCommitment.id,
                )
                .order_by(
                    WeekTask.scheduled_date.desc(),
                    WeekTask.status,
                    WeekTask.created_at,
                )
                .limit(limit)
            )
            if status is not None:
                statement = statement.where(WeekTask.status == status)
            rows = (await session.execute(statement)).all()
            counts = dict(
                (
                    await session.execute(
                        select(WeekTask.status, func.count(WeekTask.id)).group_by(
                            WeekTask.status
                        )
                    )
                ).all()
            )
            return {
                "timezone": settings.timezone,
                "counts": {
                    "active": int(counts.get("active", 0)),
                    "parked": int(counts.get("parked", 0)),
                    "completed": int(counts.get("completed", 0)),
                    "cancelled": int(counts.get("cancelled", 0)),
                    "total": int(sum(counts.values())),
                },
                "tasks": [
                    _task_payload(
                        task,
                        week_start=placement.week_start,
                        commitment_title=(
                            commitment.title if commitment is not None else None
                        ),
                    )
                    for task, placement, commitment in rows
                ],
            }

    @dashboard.post(
        "/api/dashboard/tasks/{task_id}/complete",
        dependencies=[Depends(require_token)],
    )
    async def complete_task(
        task_id: str,
        body: CompleteTaskBody | None = None,
    ) -> dict[str, Any]:
        try:
            result = await app.domain.complete_task(
                CompleteTaskRequest(
                    task_id=task_id,
                    actual_min=body.actual_min if body else None,
                )
            )
        except DomainError as exc:
            status_code = 404 if exc.code == "NOT_FOUND" else 409
            raise HTTPException(status_code=status_code, detail=exc.message) from exc
        return {
            "ok": True,
            "task_id": result.get("task_id", task_id),
            "status": result.get("status", "completed"),
            "already": result.get("already"),
        }

    @dashboard.get(
        "/api/dashboard/reconciliations",
        dependencies=[Depends(require_token)],
    )
    async def reconciliations(
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        tz = ZoneInfo(settings.timezone)
        async with app.db.locked_session() as session:
            plans = (
                await session.execute(
                    select(DayPlan)
                    .where(DayPlan.source == "reconcile")
                    .order_by(DayPlan.local_date.desc(), DayPlan.revision.desc())
                    .limit(limit)
                )
            ).scalars().all()
            history: list[dict[str, Any]] = []
            for plan in plans:
                rows = (
                    await session.execute(
                        select(DayPlanItem, WeekTask)
                        .join(WeekTask, DayPlanItem.task_id == WeekTask.id)
                        .where(DayPlanItem.day_plan_id == plan.id)
                        .order_by(DayPlanItem.position)
                    )
                ).all()
                audit = await session.scalar(
                    select(AuditEvent)
                    .where(
                        AuditEvent.action == "reconcile_proposal_approved",
                        AuditEvent.entity_id == plan.id,
                    )
                    .order_by(AuditEvent.created_at.desc())
                    .limit(1)
                )
                history.append(
                    {
                        "id": plan.id,
                        "date": plan.local_date.isoformat(),
                        "revision": plan.revision,
                        "battery": plan.battery,
                        "approved_at": (
                            plan.approved_at.isoformat()
                            if plan.approved_at
                            else None
                        ),
                        "latest_wake_display": _time_label(
                            plan.latest_wake_utc, tz
                        ),
                        "summary": audit.summary_redacted if audit else None,
                        "items": [
                            {
                                **_task_payload(task),
                                "disposition": item.disposition,
                                "position": item.position,
                                "outcome": item.outcome,
                                "planned_est_min": item.planned_est_min,
                                "planned_start_display": _time_label(
                                    item.planned_start_utc, tz
                                ),
                                "planned_end_display": _time_label(
                                    item.planned_end_utc, tz
                                ),
                            }
                            for item, task in rows
                        ],
                    }
                )
            return {
                "timezone": settings.timezone,
                "reconciliations": history,
            }

    return dashboard
