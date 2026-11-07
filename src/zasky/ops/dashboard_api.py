"""Authenticated owner dashboard API for the Vercel frontend.

The dashboard is a convenience surface over the same deterministic domain
service. It never exposes planning data without the dashboard bearer token and
it never lets the browser write task status without an explicit owner action.
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import func, select

from zasky.agent.execution import ExecutionSubAgentError
from zasky.domain.errors import DomainError
from zasky.domain.schemas import AddCommitmentRequest, CompleteTaskRequest
from zasky.integrations.calendar import (
    build_calendar_feed,
    google_calendar_quick_add_url,
)
from zasky.integrations.discord import DiscordNotificationError
from zasky.planner.core import as_utc
from zasky.storage.models import (
    AuditEvent,
    DayPlan,
    DayPlanItem,
    FixedEvent,
    MonthCommitment,
    WeekPlacement,
    WeekTask,
    YearGoal,
)

if TYPE_CHECKING:
    from zasky.app import ZaskyApp


class CompleteTaskBody(BaseModel):
    actual_min: int | None = Field(default=None, ge=0, le=100000)


class ExecutionResultBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=6000)
    task_id: str | None = Field(default=None, max_length=36)


class GoalCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    year: int = Field(ge=2000, le=2200)
    evidence_of_done: str = Field(min_length=1, max_length=1000)


class CommitmentCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    year: int = Field(ge=2000, le=2200)
    month: int = Field(ge=1, le=12)
    goal_id: str | None = None
    est_min: int = Field(gt=0, le=100000)
    deadline_local_date: date | None = None
    consequence: str | None = Field(default=None, max_length=1000)
    priority: Literal["high", "normal", "low"] = "normal"


class TaskCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    est_min: int = Field(gt=0, le=100000)
    scheduled_date: date | None = None
    commitment_id: str | None = None


class DelegateBody(BaseModel):
    instruction: str | None = Field(default=None, max_length=2000)


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


def _task_calendar_url(
    task: WeekTask,
    tz: ZoneInfo,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    commitment_title: str | None = None,
) -> str:
    if start is None or end is None:
        local_start = datetime.combine(
            task.scheduled_date, time(9, 0), tzinfo=tz
        )
        start = local_start.astimezone(UTC)
        end = (local_start + timedelta(minutes=task.est_min)).astimezone(UTC)
    else:
        start = as_utc(start)
        end = as_utc(end)
    details = [
        f"Estimate: {task.est_min} minutes",
        f"Scheduled: {task.scheduled_date.isoformat()}",
    ]
    if commitment_title:
        details.append(f"Commitment: {commitment_title}")
    details.append("Created by Zasky.")
    return google_calendar_quick_add_url(
        title=task.title,
        start=start,
        end=end,
        details="\n".join(details),
    )


def _task_payload(
    task: WeekTask,
    *,
    week_start: date | None = None,
    commitment_title: str | None = None,
    google_calendar_url: str | None = None,
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
        "google_calendar_url": google_calendar_url,
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

    async def require_calendar_access(
        authorization: str | None = Header(default=None),
        token: str | None = Query(default=None),
    ) -> None:
        dashboard_token = _secret_value(settings.dashboard_api_key)
        feed_token = _secret_value(settings.calendar_feed_token)
        scheme, _, bearer = (authorization or "").partition(" ")
        if (
            scheme.lower() == "bearer"
            and bearer
            and dashboard_token
            and secrets.compare_digest(bearer.strip(), dashboard_token)
        ):
            return
        if (
            token
            and feed_token
            and secrets.compare_digest(token.strip(), feed_token)
        ):
            return
        if not dashboard_token and not feed_token:
            raise HTTPException(
                status_code=503,
                detail="Calendar feed authentication is not configured.",
            )
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid calendar feed token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    def local_today() -> date:
        return datetime.now(UTC).astimezone(ZoneInfo(settings.timezone)).date()

    def owner_identity() -> tuple[str, str]:
        return (
            settings.owner_switch_participant_id,
            settings.switch_room_id,
        )

    def raise_domain_error(exc: DomainError) -> None:
        status_code = {
            "NOT_FOUND": 404,
            "CONFLICT": 409,
            "PROPOSAL_STALE": 409,
            "PROPOSAL_EXPIRED": 409,
            "CAPACITY_EXCEEDED": 409,
            "RATE_LIMITED": 429,
            "BUDGET_EXCEEDED": 402,
            "MODEL_UNAVAILABLE": 503,
        }.get(exc.code, 400)
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    async def approve_record(request: AddCommitmentRequest) -> dict[str, Any]:
        actor_id, room_id = owner_identity()
        proposal = await app.domain.propose_record(request)
        resolved = await app.domain.resolve_proposal(
            action="approve",
            code=str(proposal["proposal"]),
            actor_id=actor_id,
            room_id=room_id,
        )
        applied = resolved.get("applied")
        if not isinstance(applied, dict):
            raise HTTPException(
                status_code=409,
                detail="The record proposal did not apply.",
            )
        return applied

    @dashboard.get(
        "/api/dashboard/calendar.ics",
        dependencies=[Depends(require_calendar_access)],
    )
    async def calendar_feed() -> Response:
        content = await build_calendar_feed(app.db, settings)
        return Response(
            content=content,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": 'inline; filename="zasky-calendar.ics"',
                "Cache-Control": "no-cache, max-age=0",
            },
        )

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
                    **_task_payload(
                        task,
                        google_calendar_url=_task_calendar_url(
                            task,
                            tz,
                            start=item.planned_start_utc,
                            end=item.planned_end_utc,
                        ),
                    ),
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

    @dashboard.get("/api/dashboard/goals", dependencies=[Depends(require_token)])
    async def goals() -> dict[str, Any]:
        async with app.db.locked_session() as session:
            rows = (
                await session.execute(
                    select(YearGoal).order_by(
                        YearGoal.year.desc(), YearGoal.created_at
                    )
                )
            ).scalars().all()
            return {
                "goals": [
                    {
                        "id": goal.id,
                        "title": goal.title,
                        "year": goal.year,
                        "evidence_of_done": goal.evidence_of_done,
                        "status": goal.status,
                    }
                    for goal in rows
                ]
            }

    @dashboard.post(
        "/api/dashboard/goals", dependencies=[Depends(require_token)]
    )
    async def create_goal(body: GoalCreateBody) -> dict[str, Any]:
        try:
            applied = await approve_record(
                AddCommitmentRequest(
                    operation="create",
                    entry_type="year_goal",
                    title=body.title,
                    year=body.year,
                    evidence_of_done=body.evidence_of_done,
                )
            )
        except DomainError as exc:
            raise_domain_error(exc)
        return {
            "ok": True,
            "goal": {
                "id": applied["entity_id"],
                "title": body.title.strip(),
                "year": body.year,
                "evidence_of_done": body.evidence_of_done,
                "status": "active",
            },
        }

    @dashboard.get(
        "/api/dashboard/commitments",
        dependencies=[Depends(require_token)],
    )
    async def commitments() -> dict[str, Any]:
        async with app.db.locked_session() as session:
            rows = (
                await session.execute(
                    select(MonthCommitment, YearGoal)
                    .outerjoin(YearGoal, MonthCommitment.goal_id == YearGoal.id)
                    .order_by(
                        MonthCommitment.year.desc(),
                        MonthCommitment.month.desc(),
                        MonthCommitment.created_at,
                    )
                )
            ).all()
            return {
                "commitments": [
                    {
                        "id": commitment.id,
                        "title": commitment.title,
                        "year": commitment.year,
                        "month": commitment.month,
                        "goal_id": commitment.goal_id,
                        "goal_title": goal.title if goal is not None else None,
                        "est_total_min": commitment.est_total_min,
                        "deadline_local_date": (
                            commitment.deadline_local_date.isoformat()
                            if commitment.deadline_local_date
                            else None
                        ),
                        "priority": commitment.priority,
                        "status": commitment.status,
                    }
                    for commitment, goal in rows
                ]
            }

    @dashboard.post(
        "/api/dashboard/commitments",
        dependencies=[Depends(require_token)],
    )
    async def create_commitment(body: CommitmentCreateBody) -> dict[str, Any]:
        try:
            applied = await approve_record(
                AddCommitmentRequest(
                    operation="create",
                    entry_type="month_commitment",
                    title=body.title,
                    year=body.year,
                    month=body.month,
                    goal_id=body.goal_id,
                    est_min=body.est_min,
                    deadline_local_date=body.deadline_local_date,
                    consequence=body.consequence,
                    priority=body.priority,
                )
            )
        except DomainError as exc:
            raise_domain_error(exc)
        return {
            "ok": True,
            "commitment": {
                "id": applied["entity_id"],
                "title": body.title.strip(),
                "year": body.year,
                "month": body.month,
                "goal_id": body.goal_id,
                "est_total_min": body.est_min,
                "deadline_local_date": (
                    body.deadline_local_date.isoformat()
                    if body.deadline_local_date
                    else None
                ),
                "priority": body.priority,
                "status": "active",
            },
        }

    @dashboard.post("/api/dashboard/tasks", dependencies=[Depends(require_token)])
    async def create_task(body: TaskCreateBody) -> dict[str, Any]:
        try:
            task = await app.domain.add_week_task(
                title=body.title,
                est_min=body.est_min,
                scheduled_date=body.scheduled_date,
                commitment_id=body.commitment_id,
            )
        except DomainError as exc:
            raise_domain_error(exc)
        return {"ok": True, "task": task}

    @dashboard.get("/api/dashboard/tasks", dependencies=[Depends(require_token)])
    async def tasks(
        status: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        allowed = {"active", "parked", "completed", "cancelled"}
        if status is not None and status not in allowed:
            raise HTTPException(status_code=400, detail="Unknown task status.")
        tz = ZoneInfo(settings.timezone)
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
            task_ids = [task.id for task, _placement, _commitment in rows]
            planned: dict[str, tuple[datetime | None, datetime | None]] = {}
            if task_ids:
                plan_rows = (
                    await session.execute(
                        select(
                            DayPlanItem.task_id,
                            DayPlanItem.planned_start_utc,
                            DayPlanItem.planned_end_utc,
                        )
                        .join(DayPlan, DayPlanItem.day_plan_id == DayPlan.id)
                        .where(
                            DayPlan.status == "approved",
                            DayPlanItem.task_id.in_(task_ids),
                            DayPlanItem.planned_start_utc.is_not(None),
                            DayPlanItem.planned_end_utc.is_not(None),
                        )
                        .order_by(
                            DayPlan.local_date.desc(),
                            DayPlan.revision.desc(),
                        )
                    )
                ).all()
                for task_id, start, end in plan_rows:
                    planned.setdefault(task_id, (start, end))
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
                        google_calendar_url=_task_calendar_url(
                            task,
                            tz,
                            start=planned.get(task.id, (None, None))[0],
                            end=planned.get(task.id, (None, None))[1],
                            commitment_title=(
                                commitment.title
                                if commitment is not None
                                else None
                            ),
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

    @dashboard.post(
        "/api/dashboard/delegate/{task_id}",
        dependencies=[Depends(require_token)],
    )
    async def delegate(
        task_id: str,
        body: DelegateBody | None = None,
    ) -> dict[str, Any]:
        try:
            result = await app.delegate_task(
                task_id,
                body.instruction if body else None,
            )
        except DomainError as exc:
            raise_domain_error(exc)
        except ExecutionSubAgentError as exc:
            status_code = {
                "RATE_LIMITED": 429,
                "BUDGET_EXCEEDED": 402,
                "MODEL_UNAVAILABLE": 503,
                "CONFLICT": 409,
            }.get(exc.code, 502)
            raise HTTPException(
                status_code=status_code, detail=exc.message
            ) from exc
        return {"ok": True, **result}

    @dashboard.post(
        "/api/internal/execution-results",
        dependencies=[Depends(require_token)],
    )
    async def execution_result(body: ExecutionResultBody) -> dict[str, Any]:
        """Accept a result from the Execution Sub-Agent and post it to Discord."""
        try:
            delivered = await app.publish_execution_result(
                title=body.title,
                body=body.body,
                task_id=body.task_id,
            )
        except DiscordNotificationError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Execution result delivery failed ({exc.code}).",
            ) from exc
        if not delivered:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Execution result routing is not configured. Set "
                    "DISCORD_BOT_TOKEN and DISCORD_AI_WORKSPACE_CHANNEL_ID."
                ),
            )
        return {
            "ok": True,
            "delivered": True,
            "channel": "ai-workspace",
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
                                **_task_payload(
                                    task,
                                    google_calendar_url=_task_calendar_url(
                                        task,
                                        tz,
                                        start=item.planned_start_utc,
                                        end=item.planned_end_utc,
                                    ),
                                ),
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
