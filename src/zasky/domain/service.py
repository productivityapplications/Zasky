"""Deterministic domain operations behind Zasky's seven tools.

The model never writes here directly. Every proposal is validated, stored as a
pending proposal and applied only by the deterministic approval transaction.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.domain.schemas import (
    AddCommitmentRequest,
    CompleteTaskRequest,
    ParkTaskRequest,
    PlaceWeekRequest,
    PlanDayRequest,
    QueryRequest,
    ReconcileRequest,
)
from zasky.planner.core import (
    as_utc,
    backplan,
    daily_capacity,
    month_capacity,
    remaining_week_capacity,
    schedule_tasks,
    week_capacity,
    week_feasibility,
    week_start_for,
)
from zasky.storage.database import Database
from zasky.storage.models import (
    AuditEvent,
    DayPlan,
    DayPlanItem,
    FixedEvent,
    MonthCommitment,
    OwnerConfig,
    PendingProposal,
    PlanningScopeRevision,
    WeekPlacement,
    WeekTask,
    YearGoal,
)

_PRIORITY = {"high": 0, "normal": 1, "low": 2}
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_UTC = UTC


def _now() -> datetime:
    return datetime.now(_UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=_UTC) if value.tzinfo is None else value.astimezone(_UTC)


def normalize_title(title: str) -> str:
    return " ".join(title.strip().lower().split())


def _valid_day(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


class DomainService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._db = database
        self._settings = settings

    # ------------------------------------------------------------------ helpers

    async def _config(self, session: AsyncSession) -> OwnerConfig:
        config = await session.get(OwnerConfig, 1)
        if config is None:
            raise DomainError(
                "STORAGE_UNAVAILABLE",
                "Owner configuration is not initialized. Run the setup/migration step.",
            )
        return config

    async def _scope(self, session: AsyncSession, scope_key: str) -> int:
        row = await session.get(PlanningScopeRevision, scope_key)
        if row is None:
            row = PlanningScopeRevision(
                scope_key=scope_key, revision=1, updated_at=_now()
            )
            session.add(row)
            await session.flush()
            return 1
        return row.revision

    async def _bump(self, session: AsyncSession, scope_key: str) -> int:
        row = await session.get(PlanningScopeRevision, scope_key)
        if row is None:
            row = PlanningScopeRevision(
                scope_key=scope_key, revision=1, updated_at=_now()
            )
            session.add(row)
        else:
            row.revision += 1
            row.updated_at = _now()
        await session.flush()
        return row.revision

    async def _audit(
        self,
        session: AsyncSession,
        *,
        action: str,
        entity_type: str | None,
        entity_id: str | None,
        summary: str,
        actor_id: str | None = None,
    ) -> None:
        session.add(
            AuditEvent(
                id=str(uuid.uuid4()),
                actor_type="owner" if actor_id else "system",
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary_redacted=summary[:300],
                correlation_id=uuid.uuid4().hex,
            )
        )

    async def _fixed_events(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> list[FixedEvent]:
        config = await self._config(session)
        tz = ZoneInfo(config.timezone)
        start_utc = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(_UTC)
        end_utc = datetime.combine(
            end_date + timedelta(days=1), time.min, tzinfo=tz
        ).astimezone(_UTC)
        rows = (
            await session.execute(
                select(FixedEvent).where(FixedEvent.status == "active")
            )
        ).scalars()
        return [
            event
            for event in rows
            if _aware(event.starts_at_utc) < end_utc
            and _aware(event.ends_at_utc) > start_utc
        ]

    async def _week_tasks(
        self, session: AsyncSession, week_start: date
    ) -> list[tuple[WeekTask, MonthCommitment | None]]:
        result = await session.execute(
            select(WeekTask, MonthCommitment)
            .join(WeekPlacement, WeekTask.placement_id == WeekPlacement.id)
            .outerjoin(
                MonthCommitment, WeekPlacement.commitment_id == MonthCommitment.id
            )
            .where(
                WeekPlacement.week_start == week_start,
                WeekPlacement.status == "active",
            )
        )
        return [(task, commitment) for task, commitment in result.all()]

    async def _task(
        self, session: AsyncSession, task_id: str
    ) -> tuple[WeekTask, WeekPlacement, MonthCommitment | None]:
        result = await session.execute(
            select(WeekTask, WeekPlacement, MonthCommitment)
            .join(WeekPlacement, WeekTask.placement_id == WeekPlacement.id)
            .outerjoin(
                MonthCommitment, WeekPlacement.commitment_id == MonthCommitment.id
            )
            .where(WeekTask.id == task_id)
        )
        row = result.first()
        if row is None:
            raise DomainError("NOT_FOUND", "That task does not exist.")
        task, placement, commitment = row
        return task, placement, commitment

    async def _commitment_scopes(
        self, session: AsyncSession, commitment_id: str
    ) -> list[str]:
        placements = (
            await session.execute(
                select(WeekPlacement).where(
                    WeekPlacement.commitment_id == commitment_id
                )
            )
        ).scalars().all()
        scopes: list[str] = []
        for placement in placements:
            scopes.append(f"week:{placement.week_start.isoformat()}")
            tasks = (
                await session.execute(
                    select(WeekTask).where(WeekTask.placement_id == placement.id)
                )
            ).scalars().all()
            scopes.extend(
                f"day:{task.scheduled_date.isoformat()}" for task in tasks
            )
        return sorted(set(scopes))

    async def _new_code(self, session: AsyncSession) -> str:
        for _ in range(30):
            code = "ZK-" + "".join(
                secrets.choice(_CODE_ALPHABET) for _ in range(4)
            )
            exists = await session.scalar(
                select(PendingProposal.id).where(PendingProposal.code == code)
            )
            if exists is None:
                return code
        raise DomainError("CONFLICT", "Could not generate a unique proposal code.")

    async def _make_proposal(
        self,
        session: AsyncSession,
        *,
        proposal_type: str,
        payload: dict[str, Any],
        expected_scopes: list[str],
        affected_scopes: list[str],
        ttl: timedelta,
    ) -> dict[str, Any]:
        now = _now()
        expected: dict[str, int] = {}
        for scope_key in expected_scopes:
            expected[scope_key] = await self._scope(session, scope_key)
        primary = expected_scopes[0]
        code = await self._new_code(session)
        document = {
            "version": 1,
            "kind": proposal_type,
            "expected_revisions": expected,
            "affected_scopes": affected_scopes,
            **payload,
        }
        proposal = PendingProposal(
            id=str(uuid.uuid4()),
            code=code,
            proposal_type=proposal_type,
            status="pending",
            payload_json=json.dumps(document, default=str),
            payload_schema_version=1,
            base_revision=expected[primary],
            scope_key=primary,
            expires_at=now + ttl,
            created_at=now,
        )
        session.add(proposal)
        await session.flush()
        return {
            "ok": True,
            "proposal": code,
            "proposal_type": proposal_type,
            "scope_key": primary,
            "expires_at": (now + ttl).isoformat(),
            "payload": document,
        }

    # ------------------------------------------------------------------- record

    async def propose_record(self, request: AddCommitmentRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            config = await self._config(session)
            entity_id = request.entity_id or str(uuid.uuid4())
            extra_scopes: list[str] = []
            payload: dict[str, Any] = {
                "operation": request.operation,
                "entry_type": request.entry_type,
                "entity_id": entity_id,
                "title": request.title.strip(),
                "priority": request.priority,
                "status": request.status,
                "year": request.year,
                "month": request.month,
                "goal_id": request.goal_id,
                "evidence_of_done": request.evidence_of_done,
                "est_min": request.est_min,
                "deadline_local_date": (
                    request.deadline_local_date.isoformat()
                    if request.deadline_local_date
                    else None
                ),
                "consequence": request.consequence,
                "starts_at": request.starts_at.isoformat() if request.starts_at else None,
                "ends_at": request.ends_at.isoformat() if request.ends_at else None,
            }

            if request.entry_type == "year_goal":
                if request.operation == "create":
                    if request.year is None:
                        raise DomainError("INVALID_INPUT", "A goal needs a year.")
                    scope = f"goal:{request.year}"
                    await self._validate_goal_create(session, request, entity_id)
                else:
                    await self._validate_goal_update(session, request)
                    goal = await session.get(YearGoal, entity_id)
                    if goal is None:
                        raise DomainError("NOT_FOUND", "That goal does not exist.")
                    scope = f"goal:{goal.year}"
            elif request.entry_type == "month_commitment":
                if request.operation == "create":
                    if request.year is None or request.month is None:
                        raise DomainError("INVALID_INPUT", "A commitment needs year and month.")
                    scope = f"month:{request.year}-{request.month:02d}"
                    await self._validate_commitment_create(session, request)
                else:
                    await self._validate_commitment_update(session, request)
                    commitment = await session.get(MonthCommitment, entity_id)
                    if commitment is None:
                        raise DomainError("NOT_FOUND", "That commitment does not exist.")
                    scope = f"month:{commitment.year}-{commitment.month:02d}"
                    extra_scopes = await self._commitment_scopes(session, entity_id)
            else:
                scope = "calendar"
                await self._validate_fixed_event(session, request, config)

            result = await self._make_proposal(
                session,
                proposal_type="record",
                payload=payload,
                expected_scopes=[scope, *extra_scopes],
                affected_scopes=[scope, *extra_scopes],
                ttl=timedelta(minutes=30),
            )
            await session.commit()
            return result

    async def _validate_goal_create(
        self,
        session: AsyncSession,
        request: AddCommitmentRequest,
        entity_id: str,
    ) -> None:
        if request.year is None or not (request.evidence_of_done or "").strip():
            raise DomainError("INVALID_INPUT", "A goal needs a year and evidence of done.")
        count = (
            await session.execute(
                select(YearGoal.id).where(
                    YearGoal.year == request.year, YearGoal.status == "active"
                )
            )
        ).scalars().all()
        if len(count) >= 5 and entity_id not in count:
            raise DomainError(
                "CONFLICT",
                "There are already five active goals for that year. Retire or replace one first.",
            )
        duplicate = await session.scalar(
            select(YearGoal.id).where(
                YearGoal.year == request.year,
                YearGoal.normalized_title == normalize_title(request.title),
            )
        )
        if duplicate is not None:
            raise DomainError("CONFLICT", "A goal with that title already exists.")

    async def _validate_goal_update(
        self, session: AsyncSession, request: AddCommitmentRequest
    ) -> None:
        goal = await session.get(YearGoal, request.entity_id)
        if goal is None:
            raise DomainError("NOT_FOUND", "That goal does not exist.")
        duplicate = await session.scalar(
            select(YearGoal.id).where(
                YearGoal.year == goal.year,
                YearGoal.normalized_title == normalize_title(request.title),
                YearGoal.id != goal.id,
            )
        )
        if duplicate is not None:
            raise DomainError("CONFLICT", "A goal with that title already exists.")
        if request.status is not None:
            allowed = {"active", "achieved", "retired"}
            if request.status not in allowed:
                raise DomainError("INVALID_INPUT", "Invalid goal status.")
            if goal.status != "active" and request.status != goal.status:
                raise DomainError("CONFLICT", "A goal cannot move back to active.")

    async def _validate_commitment_create(
        self, session: AsyncSession, request: AddCommitmentRequest
    ) -> None:
        if request.year is None or request.month is None or request.est_min is None:
            raise DomainError(
                "INVALID_INPUT", "A commitment needs year, month and a positive estimate."
            )
        if request.goal_id is not None:
            goal = await session.get(YearGoal, request.goal_id)
            if goal is None or goal.status != "active":
                raise DomainError(
                    "INVALID_INPUT", "The linked goal must exist and be active."
                )

    async def _validate_commitment_update(
        self, session: AsyncSession, request: AddCommitmentRequest
    ) -> None:
        commitment = await session.get(MonthCommitment, request.entity_id)
        if commitment is None:
            raise DomainError("NOT_FOUND", "That commitment does not exist.")
        if request.goal_id is not None:
            goal = await session.get(YearGoal, request.goal_id)
            if goal is None or goal.status != "active":
                raise DomainError("INVALID_INPUT", "The linked goal must be active.")
        if request.status is not None:
            if request.status not in {
                "active",
                "completed",
                "renegotiated",
                "cancelled",
            }:
                raise DomainError("INVALID_INPUT", "Invalid commitment status.")
            if commitment.status != "active" and request.status != commitment.status:
                raise DomainError("CONFLICT", "That commitment is already resolved.")

    async def _validate_fixed_event(
        self,
        session: AsyncSession,
        request: AddCommitmentRequest,
        config: OwnerConfig,
    ) -> None:
        if request.operation == "create":
            if request.starts_at is None or request.ends_at is None:
                raise DomainError(
                    "INVALID_INPUT", "A fixed event needs explicit start and end times."
                )
            if request.starts_at.tzinfo is None or request.ends_at.tzinfo is None:
                raise DomainError(
                    "INVALID_INPUT", "Fixed-event times must include an explicit offset."
                )
            if request.ends_at <= request.starts_at:
                raise DomainError("INVALID_INPUT", "A fixed event must end after it starts.")
        else:
            event = await session.get(FixedEvent, request.entity_id)
            if event is None:
                raise DomainError("NOT_FOUND", "That fixed event does not exist.")
            if request.status not in (None, "active", "cancelled"):
                raise DomainError("INVALID_INPUT", "Invalid fixed-event status.")
            if request.starts_at is not None and _aware(request.starts_at) != _aware(
                event.starts_at_utc
            ):
                raise DomainError(
                    "INVALID_INPUT",
                    "Fixed events are immutable; cancel and create a replacement explicitly.",
                )
            if request.ends_at is not None and _aware(request.ends_at) != _aware(
                event.ends_at_utc
            ):
                raise DomainError(
                    "INVALID_INPUT",
                    "Fixed events are immutable; cancel and create a replacement explicitly.",
                )

    async def _apply_record(
        self, session: AsyncSession, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        entry_type = payload["entry_type"]
        operation = payload["operation"]
        entity_id = payload["entity_id"]
        goal: YearGoal | None
        commitment: MonthCommitment | None
        event: FixedEvent | None
        if entry_type == "year_goal":
            if operation == "create":
                goal = YearGoal(
                    id=entity_id,
                    year=payload["year"],
                    title=payload["title"],
                    normalized_title=normalize_title(payload["title"]),
                    evidence_of_done=payload["evidence_of_done"],
                    status="active",
                )
                session.add(goal)
            else:
                goal = await session.get(YearGoal, entity_id)
                if goal is None:
                    raise DomainError("NOT_FOUND", "That goal no longer exists.")
                goal.title = payload["title"]
                goal.normalized_title = normalize_title(payload["title"])
                if payload.get("evidence_of_done"):
                    goal.evidence_of_done = payload["evidence_of_done"]
                if payload.get("status") and payload["status"] != goal.status:
                    goal.status = payload["status"]
                    now = _now()
                    if goal.status == "achieved":
                        goal.achieved_at = now
                    elif goal.status == "retired":
                        goal.retired_at = now
                goal.updated_at = _now()
        elif entry_type == "month_commitment":
            if operation == "create":
                commitment = MonthCommitment(
                    id=entity_id,
                    goal_id=payload.get("goal_id"),
                    year=payload["year"],
                    month=payload["month"],
                    title=payload["title"],
                    est_total_min=payload["est_min"],
                    deadline_local_date=(
                        date.fromisoformat(str(payload["deadline_local_date"]))
                        if payload.get("deadline_local_date")
                        else None
                    ),
                    consequence=payload.get("consequence"),
                    priority=payload["priority"],
                    status="active",
                )
                session.add(commitment)
            else:
                commitment = await session.get(MonthCommitment, entity_id)
                if commitment is None:
                    raise DomainError("NOT_FOUND", "That commitment no longer exists.")
                commitment.title = payload["title"]
                if payload.get("est_min") is not None:
                    commitment.est_total_min = payload["est_min"]
                if payload.get("goal_id") is not None:
                    commitment.goal_id = payload["goal_id"]
                if payload.get("deadline_local_date") is not None:
                    commitment.deadline_local_date = date.fromisoformat(
                        str(payload["deadline_local_date"])
                    )
                if payload.get("consequence") is not None:
                    commitment.consequence = payload["consequence"]
                if payload.get("status") and payload["status"] != commitment.status:
                    commitment.status = payload["status"]
                    if commitment.status == "completed":
                        commitment.completed_at = _now()
                    if commitment.status == "cancelled":
                        placements = (
                            await session.execute(
                                select(WeekPlacement).where(
                                    WeekPlacement.commitment_id == commitment.id
                                )
                            )
                        ).scalars().all()
                        for placement in placements:
                            placement.status = "cancelled"
                            tasks = (
                                await session.execute(
                                    select(WeekTask).where(
                                        WeekTask.placement_id == placement.id
                                    )
                                )
                            ).scalars().all()
                            for task in tasks:
                                task.status = "cancelled"
                                task.updated_at = _now()
                commitment.updated_at = _now()
        else:
            if operation == "create":
                event = FixedEvent(
                    id=entity_id,
                    title=payload["title"],
                    starts_at_utc=_aware(datetime.fromisoformat(str(payload["starts_at"]))),
                    ends_at_utc=_aware(datetime.fromisoformat(str(payload["ends_at"]))),
                    status="active",
                    source="owner",
                )
                session.add(event)
            else:
                event = await session.get(FixedEvent, entity_id)
                if event is None:
                    raise DomainError("NOT_FOUND", "That fixed event no longer exists.")
                if payload.get("status") == "cancelled":
                    event.status = "cancelled"
                    event.updated_at = _now()
                elif payload.get("status") == "active":
                    raise DomainError("CONFLICT", "A cancelled fixed event cannot be revived.")
        await self._audit(
            session,
            action="record_proposal_approved",
            entity_type=entry_type,
            entity_id=entity_id,
            summary=f"approved {operation} {entry_type}",
            actor_id=actor_id,
        )
        return {"entry_type": entry_type, "entity_id": entity_id, "operation": operation}

    # -------------------------------------------------------------- week tool

    async def propose_week(self, request: PlaceWeekRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            config = await self._config(session)
            expected_week_start = week_start_for(
                request.week_start, config.week_start_weekday
            )
            if expected_week_start != request.week_start:
                raise DomainError(
                    "INVALID_INPUT",
                    f"That date is not the configured week start ({config.week_start_weekday}).",
                )
            fixed_events = await self._fixed_events(
                session, request.week_start, request.week_start + timedelta(days=6)
            )
            week = week_capacity(request.week_start, config, fixed_events)
            existing = await self._week_tasks(session, request.week_start)
            existing_work = sum(
                task.est_min
                for task, _commitment in existing
                if task.status in {"active", "parked"}
            )
            existing_by_date: dict[date, int] = {}
            for task, _commitment in existing:
                if task.status in {"active", "parked"}:
                    existing_by_date[task.scheduled_date] = (
                        existing_by_date.get(task.scheduled_date, 0) + task.est_min
                    )

            selected_by_date: dict[date, int] = {}
            groups: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
            commitments: dict[str, MonthCommitment] = {}
            new_work = 0
            for item in request.tasks:
                title = item.task_title.strip()
                if not title:
                    raise DomainError("INVALID_INPUT", "Task titles must be supplied by the owner.")
                if item.ad_hoc:
                    if item.commitment_id is not None:
                        raise DomainError(
                            "INVALID_INPUT", "An ad hoc task must not link a commitment."
                        )
                else:
                    if item.commitment_id is None:
                        raise DomainError(
                            "INVALID_INPUT", "A normal task requires a commitment."
                        )
                    commitment = commitments.get(item.commitment_id)
                    if commitment is None:
                        commitment = await session.get(
                            MonthCommitment, item.commitment_id
                        )
                        if commitment is None or commitment.status != "active":
                            raise DomainError(
                                "INVALID_INPUT", "The commitment must exist and be active."
                            )
                        commitments[item.commitment_id] = commitment
                    existing_placement = await session.scalar(
                        select(WeekPlacement.id).where(
                            WeekPlacement.commitment_id == item.commitment_id,
                            WeekPlacement.week_start == request.week_start,
                            WeekPlacement.status == "active",
                        )
                    )
                    if existing_placement is not None:
                        raise DomainError(
                            "CONFLICT",
                            "That commitment already has a placement in this week.",
                        )

                chosen_date = item.scheduled_date
                if chosen_date is not None:
                    if not (
                        request.week_start
                        <= chosen_date
                        <= request.week_start + timedelta(days=6)
                    ):
                        raise DomainError(
                            "INVALID_INPUT", "A task date must fall inside the selected week."
                        )
                    budget = daily_capacity(chosen_date, config, fixed_events).budget_min
                    load = existing_by_date.get(chosen_date, 0) + selected_by_date.get(
                        chosen_date, 0
                    )
                    if load + item.est_min > budget:
                        raise DomainError(
                            "CAPACITY_EXCEEDED",
                            f"That date has {max(0, budget - load)} planning minutes left; "
                            f"the task needs {item.est_min}.",
                            details={"date": chosen_date.isoformat()},
                        )
                else:
                    candidates = []
                    for offset in range(7):
                        candidate_date = request.week_start + timedelta(days=offset)
                        budget = daily_capacity(
                            candidate_date, config, fixed_events
                        ).budget_min
                        load = existing_by_date.get(
                            candidate_date, 0
                        ) + selected_by_date.get(candidate_date, 0)
                        if load + item.est_min <= budget:
                            candidates.append((load, candidate_date))
                    if not candidates:
                        raise DomainError(
                            "CAPACITY_EXCEEDED",
                            "No day in that week has room for that task without overbooking.",
                        )
                    chosen_date = min(candidates)[1]

                selected_by_date[chosen_date] = (
                    selected_by_date.get(chosen_date, 0) + item.est_min
                )
                new_work += item.est_min
                key = ("ad_hoc", None) if item.ad_hoc else ("commitment", item.commitment_id)
                groups.setdefault(key, []).append(
                    {
                        "task_id": str(uuid.uuid4()),
                        "title": title,
                        "est_min": item.est_min,
                        "scheduled_date": chosen_date.isoformat(),
                        "ad_hoc": item.ad_hoc,
                        "execution_type": item.execution_type,
                    }
                )

            if existing_work + new_work > week.budget_min:
                raise DomainError(
                    "CAPACITY_EXCEEDED",
                    f"The week budget is {week.budget_min} min; the pool would be "
                    f"{existing_work + new_work} min (over by "
                    f"{existing_work + new_work - week.budget_min}).",
                    details={"overage_min": existing_work + new_work - week.budget_min},
                )

            group_payload = []
            for (source_type, commitment_id), tasks in groups.items():
                group_payload.append(
                    {
                        "placement_id": str(uuid.uuid4()),
                        "source_type": source_type,
                        "commitment_id": commitment_id,
                        "tasks": tasks,
                    }
                )
            scopes = [f"week:{request.week_start.isoformat()}"]
            for commitment_id in commitments:
                scopes.append(f"commitment:{commitment_id}")
            result = await self._make_proposal(
                session,
                proposal_type="week",
                payload={
                    "week_start": request.week_start.isoformat(),
                    "groups": group_payload,
                    "estimated_work_min": existing_work + new_work,
                    "budget_min": week.budget_min,
                    "slack_min": max(0, week.budget_min - existing_work - new_work),
                    "protected_slack_min": week.slack_min,
                },
                expected_scopes=[*scopes, "calendar"],
                affected_scopes=scopes,
                ttl=timedelta(hours=24),
            )
            await session.commit()
            return result

    async def _apply_week(
        self, session: AsyncSession, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        week_start = date.fromisoformat(str(payload["week_start"]))
        for group in payload["groups"]:
            placement = WeekPlacement(
                id=group["placement_id"],
                commitment_id=group["commitment_id"],
                source_type=group["source_type"],
                week_start=week_start,
                status="active",
                revision=1,
            )
            session.add(placement)
            for task in group["tasks"]:
                scheduled = date.fromisoformat(str(task["scheduled_date"]))
                if not (week_start <= scheduled <= week_start + timedelta(days=6)):
                    raise DomainError(
                        "INVALID_INPUT", "A task date is outside the approved week."
                    )
                session.add(
                    WeekTask(
                        id=task["task_id"],
                        placement_id=placement.id,
                        title=task["title"],
                        est_min=task["est_min"],
                        scheduled_date=scheduled,
                        status="active",
                        ad_hoc=task["ad_hoc"],
                        execution_type=task.get("execution_type", "human"),
                    )
                )
        await self._audit(
            session,
            action="week_proposal_approved",
            entity_type="week",
            entity_id=week_start.isoformat(),
            summary="approved week placement",
            actor_id=actor_id,
        )
        return {"week_start": week_start.isoformat(), "groups": len(payload["groups"])}

    # --------------------------------------------------------------- day tool

    async def propose_day(self, request: PlanDayRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            config = await self._config(session)
            week_start = week_start_for(request.date, config.week_start_weekday)
            pool = await self._week_tasks(session, week_start)
            candidates = [
                (task, commitment)
                for task, commitment in pool
                if task.status == "active" and task.scheduled_date == request.date
            ]
            if not candidates:
                raise DomainError(
                    "NO_WEEK_TASKS",
                    "No active tasks are placed for that date. Plan the week first.",
                )
            fixed_events = await self._fixed_events(session, request.date, request.date)
            ranked = sorted(
                candidates,
                key=lambda pair: (
                    _PRIORITY.get(
                        pair[1].priority if pair[1] is not None else "normal", 1
                    ),
                    pair[1].deadline_local_date
                    if pair[1] is not None and pair[1].deadline_local_date
                    else date.max,
                    pair[0].created_at,
                ),
            )
            limit = 2 if request.battery == "low" else 3
            selected: list[tuple[WeekTask, MonthCommitment | None]] = []
            unplaced: list[str] = []
            for task, commitment in ranked:
                if len(selected) >= limit:
                    break
                if request.battery == "low" and selected and task.est_min > 30:
                    continue
                trial = selected + [(task, commitment)]
                scheduled = schedule_tasks(
                    request.date,
                    [(item[0].id, item[0].est_min) for item in trial],
                    config,
                    fixed_events,
                )
                if task.id in scheduled.unplaced:
                    unplaced.append(task.id)
                    continue
                selected = trial
            if not selected:
                raise DomainError(
                    "CAPACITY_EXCEEDED",
                    "None of that date's tasks fit in the remaining availability.",
                    details={"unplaced": unplaced},
                )
            schedule = schedule_tasks(
                request.date,
                [(task.id, task.est_min) for task, _commitment in selected],
                config,
                fixed_events,
            )
            scheduled_by_id = {item.task_id: item for item in schedule.scheduled}
            items = []
            for position, (task, _commitment) in enumerate(selected, start=1):
                block = scheduled_by_id.get(task.id)
                if block is None:
                    unplaced.append(task.id)
                    continue
                items.append(
                    {
                        "task_id": task.id,
                        "task_title": task.title,
                        "position": position,
                        "disposition": "must" if position == 1 else "should",
                        "planned_start_utc": block.start_utc.isoformat(),
                        "planned_end_utc": block.end_utc.isoformat(),
                        "planned_start_local": block.start_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).isoformat(),
                        "planned_end_local": block.end_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).isoformat(),
                        "planned_start_display": block.start_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).strftime("%H:%M"),
                        "planned_end_display": block.end_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).strftime("%H:%M"),
                        "planned_est_min": block.est_min,
                    }
                )
            if not items:
                raise DomainError(
                    "CAPACITY_EXCEEDED", "No selected task could be given a time block."
                )
            selected_ids = {str(item["task_id"]) for item in items}
            active_week_tasks = [
                task for task, _commitment in pool if task.status == "active"
            ]
            not_selected_count = sum(
                1 for task in active_week_tasks if task.id not in selected_ids
            )
            selected_est_min_total = sum(
                int(str(item["planned_est_min"])) for item in items
            )
            first_start = min(
                [datetime.fromisoformat(str(item["planned_start_utc"])) for item in items]
                + [
                    as_utc(event.starts_at_utc)
                    for event in fixed_events
                ]
            )
            plan = backplan(first_start, config)
            result = await self._make_proposal(
                session,
                proposal_type="day",
                payload={
                    "date": request.date.isoformat(),
                    "battery": request.battery,
                    "items": items,
                    "week_pool_active_count": len(active_week_tasks),
                    "not_selected_count": not_selected_count,
                    "selected_est_min_total": selected_est_min_total,
                    "task_cap": 2 if request.battery == "low" else 3,
                    "unplaced": unplaced,
                    "first_required_start_utc": plan.first_required_start_utc.isoformat(),
                    "latest_wake_utc": plan.latest_wake_utc.isoformat(),
                    "first_required_start_local": plan.first_required_start_utc.astimezone(
                        ZoneInfo(config.timezone)
                    ).isoformat(),
                    "latest_wake_local": plan.latest_wake_utc.astimezone(
                        ZoneInfo(config.timezone)
                    ).isoformat(),
                    "first_required_start_display": plan.first_required_start_utc.astimezone(
                        ZoneInfo(config.timezone)
                    ).strftime("%H:%M"),
                    "latest_wake_display": plan.latest_wake_utc.astimezone(
                        ZoneInfo(config.timezone)
                    ).strftime("%H:%M"),
                    "morning_prep_min": plan.morning_prep_min,
                    "commute_buffer_min": plan.commute_buffer_min,
                },
                expected_scopes=[
                    f"day:{request.date.isoformat()}",
                    f"week:{week_start.isoformat()}",
                    "calendar",
                ],
                affected_scopes=[f"day:{request.date.isoformat()}"],
                ttl=timedelta(minutes=30),
            )
            await session.commit()
            return result

    async def _replace_day_plan(
        self,
        session: AsyncSession,
        *,
        local_date: date,
        battery: str,
        source: str,
        items: list[dict[str, Any]],
        latest_wake_utc: datetime | None = None,
        first_start_utc: datetime | None = None,
    ) -> DayPlan | None:
        previous = (
            await session.execute(
                select(DayPlan).where(
                    DayPlan.local_date == local_date, DayPlan.status == "approved"
                )
            )
        ).scalars().all()
        for plan in previous:
            plan.status = "replaced"
        if not items:
            return None
        revision = (
            await session.scalar(
                select(DayPlan.revision)
                .where(DayPlan.local_date == local_date)
                .order_by(DayPlan.revision.desc())
                .limit(1)
            )
            or 0
        ) + 1
        plan = DayPlan(
            id=str(uuid.uuid4()),
            local_date=local_date,
            revision=revision,
            battery=battery,
            status="approved",
            source=source,
            earliest_required_start_utc=first_start_utc,
            latest_wake_utc=latest_wake_utc,
            approved_at=_now(),
        )
        session.add(plan)
        for item in items:
            task = await session.get(WeekTask, item["task_id"])
            if task is None or task.status != "active":
                raise DomainError(
                    "PROPOSAL_STALE", "A task in the proposal is no longer active."
                )
            if task.scheduled_date != local_date:
                raise DomainError(
                    "PROPOSAL_STALE", "A task is no longer assigned to that date."
                )
            session.add(
                DayPlanItem(
                    id=str(uuid.uuid4()),
                    day_plan_id=plan.id,
                    task_id=task.id,
                    position=item["position"],
                    disposition=item["disposition"],
                    planned_start_utc=datetime.fromisoformat(
                        item["planned_start_utc"]
                    ),
                    planned_end_utc=datetime.fromisoformat(str(item["planned_end_utc"])),
                    planned_est_min=item["planned_est_min"],
                    outcome="pending",
                )
            )
        await session.flush()
        return plan

    async def _apply_day(
        self, session: AsyncSession, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        local_date = date.fromisoformat(str(payload["date"]))
        first_start = (
            datetime.fromisoformat(str(payload["first_required_start_utc"]))
            if payload.get("first_required_start_utc")
            else None
        )
        latest_wake = (
            datetime.fromisoformat(str(payload["latest_wake_utc"]))
            if payload.get("latest_wake_utc")
            else None
        )
        plan = await self._replace_day_plan(
            session,
            local_date=local_date,
            battery=payload["battery"],
            source="plan_day",
            items=payload["items"],
            first_start_utc=first_start,
            latest_wake_utc=latest_wake,
        )
        await self._audit(
            session,
            action="day_proposal_approved",
            entity_type="day_plan",
            entity_id=plan.id if plan else local_date.isoformat(),
            summary=f"approved day plan with {len(payload['items'])} item(s)",
            actor_id=actor_id,
        )
        return {
            "date": local_date.isoformat(),
            "items": len(payload["items"]),
            "day_plan_id": plan.id if plan else None,
        }

    # --------------------------------------------------- dashboard write helpers

    async def add_week_task(
        self,
        *,
        title: str,
        est_min: int,
        week_start: date | None = None,
        scheduled_date: date | None = None,
        commitment_id: str | None = None,
        execution_type: str = "human",
    ) -> dict[str, Any]:
        """Add one owner-authored task to the current week pool.

        The dashboard is an explicit owner surface, so this applies immediately
        rather than creating a proposal. It reuses the same capacity and
        placement rules as the weekly planner and appends to an existing
        placement when the selected commitment already has one.
        """
        cleaned_title = title.strip()
        if not cleaned_title:
            raise DomainError("INVALID_INPUT", "A task needs a title.")
        if len(cleaned_title) > 200:
            raise DomainError("INVALID_INPUT", "Task titles are limited to 200 characters.")
        if est_min <= 0:
            raise DomainError("INVALID_INPUT", "A task estimate must be positive.")
        if execution_type not in {"human", "ai"}:
            raise DomainError(
                "INVALID_INPUT", "execution_type must be 'human' or 'ai'."
            )

        async with self._db.locked_session() as session:
            config = await self._config(session)
            today = datetime.now(_UTC).astimezone(ZoneInfo(config.timezone)).date()
            if week_start is not None:
                selected_week = week_start
            elif scheduled_date is not None:
                # A dashboard task submitted for a date belongs in that date's
                # week, even when the date is not in the current week.
                selected_week = week_start_for(
                    scheduled_date, config.week_start_weekday
                )
            else:
                selected_week = week_start_for(
                    today, config.week_start_weekday
                )
            normalized_week = week_start_for(
                selected_week, config.week_start_weekday
            )
            if normalized_week != selected_week:
                raise DomainError(
                    "INVALID_INPUT",
                    f"That date is not the configured week start "
                    f"({config.week_start_weekday}).",
                )
            fixed_events = await self._fixed_events(
                session, selected_week, selected_week + timedelta(days=6)
            )
            week = week_capacity(selected_week, config, fixed_events)
            existing = await self._week_tasks(session, selected_week)
            existing_work = sum(
                task.est_min
                for task, _commitment in existing
                if task.status in {"active", "parked"}
            )
            if existing_work + est_min > week.budget_min:
                raise DomainError(
                    "CAPACITY_EXCEEDED",
                    f"The week budget is {week.budget_min} min; adding this "
                    f"task would use {existing_work + est_min} min.",
                )

            chosen_date = scheduled_date
            if chosen_date is not None:
                if not (
                    selected_week
                    <= chosen_date
                    <= selected_week + timedelta(days=6)
                ):
                    raise DomainError(
                        "INVALID_INPUT",
                        "A task date must fall inside the selected week.",
                    )
                day_events = await self._fixed_events(
                    session, chosen_date, chosen_date
                )
                budget = daily_capacity(
                    chosen_date, config, day_events
                ).budget_min
                load = sum(
                    task.est_min
                    for task, _commitment in existing
                    if task.status in {"active", "parked"}
                    and task.scheduled_date == chosen_date
                )
                if load + est_min > budget:
                    raise DomainError(
                        "CAPACITY_EXCEEDED",
                        f"That date has {max(0, budget - load)} planning "
                        f"minutes left; the task needs {est_min}.",
                    )
            else:
                candidates: list[tuple[int, date]] = []
                for offset in range(7):
                    candidate = selected_week + timedelta(days=offset)
                    day_events = await self._fixed_events(
                        session, candidate, candidate
                    )
                    budget = daily_capacity(
                        candidate, config, day_events
                    ).budget_min
                    load = sum(
                        task.est_min
                        for task, _commitment in existing
                        if task.status in {"active", "parked"}
                        and task.scheduled_date == candidate
                    )
                    if load + est_min <= budget:
                        candidates.append((load, candidate))
                if not candidates:
                    raise DomainError(
                        "CAPACITY_EXCEEDED",
                        "No day in that week has room for this task.",
                    )
                chosen_date = min(candidates)[1]

            placement: WeekPlacement | None
            if commitment_id is not None:
                commitment = await session.get(MonthCommitment, commitment_id)
                if commitment is None or commitment.status != "active":
                    raise DomainError(
                        "INVALID_INPUT",
                        "The linked commitment must exist and be active.",
                    )
                placement = await session.scalar(
                    select(WeekPlacement).where(
                        WeekPlacement.commitment_id == commitment_id,
                        WeekPlacement.week_start == selected_week,
                        WeekPlacement.status == "active",
                    )
                )
                if placement is None:
                    placement = WeekPlacement(
                        id=str(uuid.uuid4()),
                        commitment_id=commitment_id,
                        source_type="commitment",
                        week_start=selected_week,
                        status="active",
                        revision=1,
                    )
                    session.add(placement)
                    await session.flush()
            else:
                placement = await session.scalar(
                    select(WeekPlacement)
                    .where(
                        WeekPlacement.commitment_id.is_(None),
                        WeekPlacement.source_type == "ad_hoc",
                        WeekPlacement.week_start == selected_week,
                        WeekPlacement.status == "active",
                    )
                    .order_by(WeekPlacement.created_at)
                    .limit(1)
                )
                if placement is None:
                    placement = WeekPlacement(
                        id=str(uuid.uuid4()),
                        commitment_id=None,
                        source_type="ad_hoc",
                        week_start=selected_week,
                        status="active",
                        revision=1,
                    )
                    session.add(placement)
                    await session.flush()

            task = WeekTask(
                id=str(uuid.uuid4()),
                placement_id=placement.id,
                title=cleaned_title,
                est_min=est_min,
                scheduled_date=chosen_date,
                status="active",
                ad_hoc=commitment_id is None,
                execution_type=execution_type,
            )
            session.add(task)
            await self._bump(session, f"week:{selected_week.isoformat()}")
            await self._bump(session, f"day:{chosen_date.isoformat()}")
            await self._audit(
                session,
                action="task_added_from_dashboard",
                entity_type="week_task",
                entity_id=task.id,
                summary="task added from owner dashboard",
                actor_id=self._settings.owner_switch_participant_id,
            )
            await session.commit()
            return {
                "id": task.id,
                "title": task.title,
                "est_min": task.est_min,
                "scheduled_date": task.scheduled_date.isoformat(),
                "status": task.status,
                "ad_hoc": task.ad_hoc,
                "execution_type": task.execution_type,
                "placement_id": placement.id,
                "week_start": selected_week.isoformat(),
            }

    async def task_detail(self, task_id: str) -> dict[str, Any]:
        """Read the bounded task, commitment and year-goal context."""
        async with self._db.locked_session() as session:
            task, placement, commitment = await self._task(session, task_id)
            goal = None
            if commitment is not None and commitment.goal_id:
                goal = await session.get(YearGoal, commitment.goal_id)
            return {
                "id": task.id,
                "title": task.title,
                "est_min": task.est_min,
                "scheduled_date": task.scheduled_date.isoformat(),
                "status": task.status,
                "ad_hoc": task.ad_hoc,
                "execution_type": task.execution_type,
                "resume_note": task.resume_note,
                "commitment_id": (
                    commitment.id if commitment is not None else None
                ),
                "commitment_title": (
                    commitment.title if commitment is not None else None
                ),
                "commitment_priority": (
                    commitment.priority if commitment is not None else None
                ),
                "commitment_deadline": (
                    commitment.deadline_local_date.isoformat()
                    if commitment is not None
                    and commitment.deadline_local_date is not None
                    else None
                ),
                "commitment_consequence": (
                    commitment.consequence if commitment is not None else None
                ),
                "goal_id": goal.id if goal is not None else None,
                "goal_title": goal.title if goal is not None else None,
                "goal_year": goal.year if goal is not None else None,
                "goal_evidence_of_done": (
                    goal.evidence_of_done if goal is not None else None
                ),
                "week_start": placement.week_start.isoformat(),
            }

    # --------------------------------------------------------- reconcile tool

    async def propose_reconcile(self, request: ReconcileRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            config = await self._config(session)
            now = _aware(request.now_iso)
            local_now = now.astimezone(ZoneInfo(config.timezone))
            local_date = request.from_date or local_now.date()
            week_start = week_start_for(local_date, config.week_start_weekday)
            if request.to_date is not None and request.to_date > week_start + timedelta(days=6):
                raise DomainError(
                    "INVALID_INPUT", "Reconcile cannot move work outside the active week."
                )
            fixed_events = await self._fixed_events(session, local_date, local_date)
            pool = await self._week_tasks(session, week_start)
            candidates = [
                (task, commitment)
                for task, commitment in pool
                if task.status == "active" and task.scheduled_date <= local_date
            ]
            if not candidates:
                raise DomainError(
                    "NO_WEEK_TASKS", "There is no active work in that week to reconcile."
                )
            ranked = sorted(
                candidates,
                key=lambda pair: (
                    0 if pair[0].scheduled_date == local_date else 1,
                    _PRIORITY.get(
                        pair[1].priority if pair[1] is not None else "normal", 1
                    ),
                    pair[1].deadline_local_date
                    if pair[1] is not None and pair[1].deadline_local_date
                    else date.max,
                    pair[0].created_at,
                ),
            )
            selected: list[tuple[WeekTask, MonthCommitment | None]] = []
            moves: list[dict[str, Any]] = []
            drops: list[dict[str, Any]] = []
            unplaced: list[str] = []
            selected_dates: dict[date, int] = {}
            for task, commitment in ranked:
                if len(selected) < 3:
                    trial = selected + [(task, commitment)]
                    schedule = schedule_tasks(
                        local_date,
                        [(item[0].id, item[0].est_min) for item in trial],
                        config,
                        fixed_events,
                        not_before=now,
                    )
                    if task.id not in schedule.unplaced:
                        selected = trial
                        continue
                # Move to a later day in the same week if it fits.
                moved = False
                for offset in range(1, 7):
                    candidate_date = local_date + timedelta(days=offset)
                    if candidate_date > week_start + timedelta(days=6):
                        break
                    day_events = await self._fixed_events(
                        session, candidate_date, candidate_date
                    )
                    budget = daily_capacity(
                        candidate_date, config, day_events
                    ).budget_min
                    load = selected_dates.get(candidate_date, 0) + sum(
                        item[0].est_min for item in candidates
                        if item[0].scheduled_date == candidate_date
                    )
                    if load + task.est_min <= budget:
                        moves.append(
                            {
                                "task_id": task.id,
                                "task_title": task.title,
                                "from_date": task.scheduled_date.isoformat(),
                                "to_date": candidate_date.isoformat(),
                            }
                        )
                        selected_dates[candidate_date] = (
                            selected_dates.get(candidate_date, 0) + task.est_min
                        )
                        moved = True
                        break
                if not moved:
                    unplaced.append(task.id)
                    drops.append({"task_id": task.id, "task_title": task.title})

            schedule = schedule_tasks(
                local_date,
                [(task.id, task.est_min) for task, _commitment in selected],
                config,
                fixed_events,
                not_before=now,
            )
            scheduled_by_id = {item.task_id: item for item in schedule.scheduled}
            items = []
            for position, (task, _commitment) in enumerate(selected, start=1):
                block = scheduled_by_id.get(task.id)
                if block is None:
                    continue
                items.append(
                    {
                        "task_id": task.id,
                        "task_title": task.title,
                        "position": position,
                        "disposition": "must" if position == 1 else "should",
                        "planned_start_utc": block.start_utc.isoformat(),
                        "planned_end_utc": block.end_utc.isoformat(),
                        "planned_start_local": block.start_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).isoformat(),
                        "planned_end_local": block.end_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).isoformat(),
                        "planned_start_display": block.start_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).strftime("%H:%M"),
                        "planned_end_display": block.end_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).strftime("%H:%M"),
                        "planned_est_min": block.est_min,
                    }
                )
            remaining_work = sum(
                task.est_min
                for task, _commitment in pool
                if task.status in {"active", "parked"}
            )
            remaining_budget = remaining_week_capacity(
                now, week_start, config, await self._fixed_events(
                    session, week_start, week_start + timedelta(days=6)
                )
            )
            feasibility = week_feasibility(remaining_work, remaining_budget)
            first_start = (
                min(
                    [datetime.fromisoformat(str(item["planned_start_utc"])) for item in items]
                    + [as_utc(event.starts_at_utc) for event in fixed_events]
                )
                if items
                else None
            )
            plan = backplan(first_start, config) if first_start else None
            result = await self._make_proposal(
                session,
                proposal_type="reconcile",
                payload={
                    "date": local_date.isoformat(),
                    "battery": "medium",
                    "items": items,
                    "moves": moves,
                    "drops": drops,
                    "unplaced": unplaced,
                    "feasibility": {
                        "status": feasibility.status,
                        "remaining_work_min": feasibility.remaining_work_min,
                        "remaining_budget_min": feasibility.remaining_budget_min,
                        "overage_min": feasibility.overage_min,
                        "arithmetic": feasibility.arithmetic,
                    },
                    "first_required_start_utc": (
                        plan.first_required_start_utc.isoformat() if plan else None
                    ),
                    "latest_wake_utc": (
                        plan.latest_wake_utc.isoformat() if plan else None
                    ),
                    "first_required_start_local": (
                        plan.first_required_start_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).isoformat()
                        if plan
                        else None
                    ),
                    "latest_wake_local": (
                        plan.latest_wake_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).isoformat()
                        if plan
                        else None
                    ),
                    "first_required_start_display": (
                        plan.first_required_start_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).strftime("%H:%M")
                        if plan
                        else None
                    ),
                    "latest_wake_display": (
                        plan.latest_wake_utc.astimezone(
                            ZoneInfo(config.timezone)
                        ).strftime("%H:%M")
                        if plan
                        else None
                    ),
                },
                expected_scopes=[
                    f"day:{local_date.isoformat()}",
                    f"week:{week_start.isoformat()}",
                    "calendar",
                ],
                affected_scopes=[
                    f"day:{local_date.isoformat()}",
                    f"week:{week_start.isoformat()}",
                ],
                ttl=timedelta(minutes=30),
            )
            await session.commit()
            return result

    async def _apply_reconcile(
        self, session: AsyncSession, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        local_date = date.fromisoformat(str(payload["date"]))
        selected_ids = {item["task_id"] for item in payload.get("items", [])}
        for move in payload.get("moves", []):
            if move["task_id"] in selected_ids:
                raise DomainError(
                    "PROPOSAL_STALE", "A task was both kept and moved."
                )
            task = await session.get(WeekTask, move["task_id"])
            if task is None or task.status != "active":
                raise DomainError(
                    "PROPOSAL_STALE", "A task in the recovery proposal is no longer active."
                )
            task.scheduled_date = date.fromisoformat(str(move["to_date"]))
            task.updated_at = _now()
        # Keeping overdue work today is a date change authorized by the
        # approved reconcile proposal, so align the task before day-plan items
        # are validated.
        for item in payload.get("items", []):
            task = await session.get(WeekTask, item["task_id"])
            if task is not None and task.scheduled_date != local_date:
                task.scheduled_date = local_date
                task.updated_at = _now()
        first_start = (
            datetime.fromisoformat(str(payload["first_required_start_utc"]))
            if payload.get("first_required_start_utc")
            else None
        )
        latest_wake = (
            datetime.fromisoformat(str(payload["latest_wake_utc"]))
            if payload.get("latest_wake_utc")
            else None
        )
        plan = await self._replace_day_plan(
            session,
            local_date=local_date,
            battery=payload["battery"],
            source="reconcile",
            items=payload["items"],
            first_start_utc=first_start,
            latest_wake_utc=latest_wake,
        )
        await self._audit(
            session,
            action="reconcile_proposal_approved",
            entity_type="day_plan",
            entity_id=plan.id if plan else local_date.isoformat(),
            summary=(
                f"approved recovery; {len(payload['items'])} kept, "
                f"{len(payload.get('moves', []))} moved"
            ),
            actor_id=actor_id,
        )
        return {
            "date": local_date.isoformat(),
            "items": len(payload["items"]),
            "moves": len(payload.get("moves", [])),
            "feasibility": payload.get("feasibility", {}).get("status"),
        }

    # ------------------------------------------------------- direct task actions

    async def park_task(self, request: ParkTaskRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            task, placement, _commitment = await self._task(session, request.task_id)
            if request.action == "park":
                if task.status in {"completed", "cancelled"}:
                    raise DomainError(
                        "CONFLICT", "A completed or cancelled task cannot be parked."
                    )
                if task.status == "parked":
                    task.resume_note = request.resume_note
                    if request.actual_min is not None:
                        task.actual_min = request.actual_min
                else:
                    task.status = "parked"
                    task.resume_note = request.resume_note
                    if request.actual_min is not None:
                        task.actual_min = request.actual_min
            else:
                if task.status == "active":
                    return {"ok": True, "already": "active", "task_id": task.id}
                if task.status != "parked":
                    raise DomainError(
                        "CONFLICT", "Only a parked task can be resumed."
                    )
                task.status = "active"
                task.resume_note = None
            task.updated_at = _now()
            await self._bump(session, f"week:{placement.week_start.isoformat()}")
            if task.scheduled_date:
                await self._bump(session, f"day:{task.scheduled_date.isoformat()}")
            await self._audit(
                session,
                action=f"task_{request.action}",
                entity_type="week_task",
                entity_id=task.id,
                summary=f"task {request.action}",
                actor_id=self._settings.owner_switch_participant_id,
            )
            await session.commit()
            return {
                "ok": True,
                "task_id": task.id,
                "status": task.status,
                "resume_note_present": bool(task.resume_note),
            }

    async def complete_task(self, request: CompleteTaskRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            task, placement, _commitment = await self._task(session, request.task_id)
            if task.status == "completed":
                return {"ok": True, "already": "completed", "task_id": task.id}
            if task.status == "cancelled":
                raise DomainError("CONFLICT", "A cancelled task cannot be completed.")
            task.status = "completed"
            task.completed_at = _now()
            if request.actual_min is not None:
                task.actual_min = request.actual_min
            task.updated_at = _now()
            items = (
                await session.execute(
                    select(DayPlanItem).where(DayPlanItem.task_id == task.id)
                )
            ).scalars().all()
            for item in items:
                item.outcome = "completed"
            await self._bump(session, f"week:{placement.week_start.isoformat()}")
            if task.scheduled_date:
                await self._bump(session, f"day:{task.scheduled_date.isoformat()}")
            await self._audit(
                session,
                action="task_completed",
                entity_type="week_task",
                entity_id=task.id,
                summary="task completed",
                actor_id=self._settings.owner_switch_participant_id,
            )
            await session.commit()
            return {"ok": True, "task_id": task.id, "status": task.status}

    # -------------------------------------------------------------- query tool

    async def query(self, request: QueryRequest) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            config = await self._config(session)
            tz = ZoneInfo(config.timezone)
            today = datetime.now(_UTC).astimezone(tz).date()
            if request.state == "goals":
                year = int(request.horizon or today.year)
                goals = (
                    await session.execute(
                        select(YearGoal).where(YearGoal.year == year)
                    )
                ).scalars().all()
                return {
                    "state": "goals",
                    "year": year,
                    "goals": [
                        {"id": goal.id, "title": goal.title, "status": goal.status}
                        for goal in goals
                    ],
                }
            if request.state == "today":
                local_date = (
                    date.fromisoformat(request.horizon) if request.horizon else today
                )
                plan = await session.scalar(
                    select(DayPlan)
                    .where(DayPlan.local_date == local_date, DayPlan.status == "approved")
                    .order_by(DayPlan.revision.desc())
                    .limit(1)
                )
                if plan is None:
                    return {"state": "today", "date": local_date.isoformat(), "items": []}
                items = (
                    await session.execute(
                        select(DayPlanItem).where(DayPlanItem.day_plan_id == plan.id)
                    )
                ).scalars().all()
                task_ids = [item.task_id for item in items]
                tasks = (
                    await session.execute(
                        select(WeekTask).where(WeekTask.id.in_(task_ids))
                    )
                ).scalars().all()
                by_id = {task.id: task for task in tasks}
                return {
                    "state": "today",
                    "date": local_date.isoformat(),
                    "battery": plan.battery,
                    "items": [
                        {
                            "id": item.task_id,
                            "title": by_id[item.task_id].title
                            if item.task_id in by_id
                            else None,
                            "disposition": item.disposition,
                            "est_min": item.planned_est_min,
                        }
                        for item in items
                    ],
                    "latest_wake_utc": (
                        plan.latest_wake_utc.isoformat() if plan.latest_wake_utc else None
                    ),
                }
            if request.state == "week":
                week_start = (
                    week_start_for(date.fromisoformat(request.horizon), config.week_start_weekday)
                    if request.horizon
                    else week_start_for(today, config.week_start_weekday)
                )
                fixed_events = await self._fixed_events(
                    session, week_start, week_start + timedelta(days=6)
                )
                capacity = week_capacity(week_start, config, fixed_events)
                pool = await self._week_tasks(session, week_start)
                work = sum(
                    task.est_min
                    for task, _commitment in pool
                    if task.status in {"active", "parked"}
                )
                return {
                    "state": "week",
                    "week_start": week_start.isoformat(),
                    "capacity": {
                        "available_min": capacity.available_min,
                        "budget_min": capacity.budget_min,
                        "slack_min": capacity.slack_min,
                    },
                    "remaining_work_min": work,
                    "status": "week_holds" if work <= capacity.budget_min else "week_at_risk",
                    "tasks": [
                        {
                            "id": task.id,
                            "title": task.title,
                            "est_min": task.est_min,
                            "scheduled_date": task.scheduled_date.isoformat(),
                            "status": task.status,
                            "execution_type": task.execution_type,
                        }
                        for task, _commitment in pool
                    ],
                }
            if request.state == "month":
                year, month = (
                    (int(request.horizon.split("-")[0]), int(request.horizon.split("-")[1]))
                    if request.horizon
                    else (today.year, today.month)
                )
                commitments = (
                    await session.execute(
                        select(MonthCommitment).where(
                            MonthCommitment.year == year,
                            MonthCommitment.month == month,
                        )
                    )
                ).scalars().all()
                month_days = [
                    date(year, month, day)
                    for day in range(1, 32)
                    if _valid_day(year, month, day)
                ]
                fixed_events = await self._fixed_events(
                    session, month_days[0], month_days[-1]
                )
                capacity = month_capacity(year, month, config, fixed_events)
                return {
                    "state": "month",
                    "year": year,
                    "month": month,
                    "budget_min": capacity.budget_min,
                    "commitments": [
                        {
                            "id": item.id,
                            "title": item.title,
                            "est_total_min": item.est_total_min,
                            "status": item.status,
                            "deadline": (
                                item.deadline_local_date.isoformat()
                                if item.deadline_local_date
                                else None
                            ),
                        }
                        for item in commitments
                    ],
                }
            if request.state == "deadlines":
                commitments = (
                    await session.execute(
                        select(MonthCommitment)
                        .where(
                            MonthCommitment.deadline_local_date.is_not(None),
                            MonthCommitment.status == "active",
                        )
                        .order_by(MonthCommitment.deadline_local_date)
                    )
                ).scalars().all()
                deadlines = []
                for item in commitments:
                    deadline = item.deadline_local_date
                    days_left = (deadline - today).days if deadline else None
                    budget = 0
                    if deadline is not None and deadline >= today:
                        cursor = today
                        while cursor <= deadline:
                            events = await self._fixed_events(
                                session, cursor, cursor
                            )
                            budget += daily_capacity(cursor, config, events).budget_min
                            cursor += timedelta(days=1)
                    placements = (
                        await session.execute(
                            select(WeekPlacement).where(
                                WeekPlacement.commitment_id == item.id
                            )
                        )
                    ).scalars().all()
                    linked_tasks: list[WeekTask] = []
                    for placement in placements:
                        linked_tasks.extend(
                            (
                                await session.execute(
                                    select(WeekTask).where(
                                        WeekTask.placement_id == placement.id
                                    )
                                )
                            ).scalars().all()
                        )
                    placed_total = sum(task.est_min for task in linked_tasks)
                    remaining_tasks = sum(
                        task.est_min
                        for task in linked_tasks
                        if task.status in {"active", "parked"}
                    )
                    unplaced_remainder = max(0, item.est_total_min - placed_total)
                    remaining_work = remaining_tasks + unplaced_remainder
                    status = (
                        "at_risk"
                        if deadline is not None and remaining_work > budget
                        else "ok"
                    )
                    deadlines.append(
                        {
                            "id": item.id,
                            "title": item.title,
                            "deadline": deadline.isoformat() if deadline else None,
                            "days_left": days_left,
                            "remaining_work_min": remaining_work,
                            "future_budget_min": budget,
                            "status": status,
                        }
                    )
                return {"state": "deadlines", "deadlines": deadlines}
            if request.state == "task":
                if not request.entity_id:
                    raise DomainError("INVALID_INPUT", "task query requires entity_id")
                task, _placement, _commitment = await self._task(session, request.entity_id)
                return {
                    "state": "task",
                    "task": {
                        "id": task.id,
                        "title": task.title,
                        "est_min": task.est_min,
                        "scheduled_date": task.scheduled_date.isoformat(),
                        "status": task.status,
                        "execution_type": task.execution_type,
                        "resume_note_present": bool(task.resume_note),
                    },
                }
            if request.state == "commitment":
                if not request.entity_id:
                    raise DomainError(
                        "INVALID_INPUT", "commitment query requires entity_id"
                    )
                commitment = await session.get(MonthCommitment, request.entity_id)
                if commitment is None:
                    raise DomainError("NOT_FOUND", "That commitment does not exist.")
                return {
                    "state": "commitment",
                    "commitment": {
                        "id": commitment.id,
                        "title": commitment.title,
                        "est_total_min": commitment.est_total_min,
                        "status": commitment.status,
                    },
                }
            if request.state == "status":
                return {
                    "state": "status",
                    "goals": len(
                        (
                            await session.execute(
                                select(YearGoal).where(YearGoal.status == "active")
                            )
                        ).scalars().all()
                    ),
                    "commitments": len(
                        (
                            await session.execute(
                                select(MonthCommitment).where(
                                    MonthCommitment.status == "active"
                                )
                            )
                        ).scalars().all()
                    ),
                }
            raise DomainError("INVALID_INPUT", "Unsupported query state.")

    # --------------------------------------------------------- proposal approval

    async def pending_codes(self) -> set[str]:
        async with self._db.locked_session() as session:
            rows = (
                await session.execute(
                    select(PendingProposal.code).where(
                        PendingProposal.status == "pending"
                    )
                )
            ).scalars().all()
            return set(rows)

    async def resolve_proposal(
        self,
        *,
        action: str,
        code: str | None,
        actor_id: str,
        room_id: str,
    ) -> dict[str, Any]:
        if action not in {"approve", "reject"}:
            raise DomainError("INVALID_INPUT", "Unknown proposal action.")
        async with self._db.locked_session() as session:
            await self._config(session)
            if code:
                proposal = await session.scalar(
                    select(PendingProposal).where(PendingProposal.code == code)
                )
            else:
                proposals = (
                    await session.execute(
                        select(PendingProposal).where(
                            PendingProposal.status == "pending"
                        )
                    )
                ).scalars().all()
                if len(proposals) != 1:
                    raise DomainError(
                        "PROPOSAL_NOT_FOUND",
                        "There is no unique pending proposal to resolve.",
                    )
                proposal = proposals[0]
            if proposal is None:
                raise DomainError("PROPOSAL_NOT_FOUND", "That proposal code does not exist.")
            if proposal.status == "approved":
                return {
                    "ok": True,
                    "already": "approved",
                    "status": "approved",
                    "proposal": proposal.code,
                }
            now = _now()
            if _aware(proposal.expires_at) <= now:
                proposal.status = "expired"
                proposal.resolved_at = now
                proposal.resolution_actor = actor_id
                proposal.resolution_reason = "expired"
                await session.commit()
                raise DomainError(
                    "PROPOSAL_EXPIRED",
                    "That proposal expired. I have not changed anything.",
                )
            if action == "reject":
                proposal.status = "rejected"
                proposal.resolved_at = now
                proposal.resolution_actor = actor_id
                proposal.resolution_reason = "owner rejected"
                await self._audit(
                    session,
                    action="proposal_rejected",
                    entity_type="pending_proposal",
                    entity_id=proposal.id,
                    summary=f"rejected {proposal.proposal_type} proposal",
                    actor_id=actor_id,
                )
                await session.commit()
                return {"ok": True, "proposal": proposal.code, "status": "rejected"}
            if proposal.status != "pending":
                raise DomainError(
                    "CONFLICT", f"That proposal is already {proposal.status}."
                )
            document = json.loads(proposal.payload_json)
            expected = document.get("expected_revisions", {})
            for scope_key, revision in expected.items():
                current = await self._scope(session, scope_key)
                if current != revision:
                    proposal.status = "stale"
                    proposal.resolved_at = now
                    proposal.resolution_actor = actor_id
                    proposal.resolution_reason = "revision changed"
                    await session.commit()
                    raise DomainError(
                        "PROPOSAL_STALE",
                        "That plan changed before approval. I have not applied it.",
                    )
            kind = proposal.proposal_type
            try:
                if kind == "record":
                    applied = await self._apply_record(session, document, actor_id)
                elif kind == "week":
                    applied = await self._apply_week(session, document, actor_id)
                elif kind == "day":
                    applied = await self._apply_day(session, document, actor_id)
                elif kind == "reconcile":
                    applied = await self._apply_reconcile(session, document, actor_id)
                else:
                    raise DomainError("INVALID_INPUT", "Unknown proposal type.")
            except DomainError:
                await session.rollback()
                raise
            for scope_key in document.get("affected_scopes", []):
                await self._bump(session, scope_key)
            proposal.status = "approved"
            proposal.resolved_at = now
            proposal.resolution_actor = actor_id
            proposal.resolution_reason = "owner approved"
            await self._audit(
                session,
                action="proposal_approved",
                entity_type="pending_proposal",
                entity_id=proposal.id,
                summary=f"approved {kind} proposal",
                actor_id=actor_id,
            )
            await session.commit()
            return {
                "ok": True,
                "proposal": proposal.code,
                "proposal_type": kind,
                "status": "approved",
                "applied": applied,
            }
