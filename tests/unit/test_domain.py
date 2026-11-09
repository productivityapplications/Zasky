from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select

from tests.fixtures.identities import OWNER_ID, ROOM_ID
from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.domain.schemas import (
    AddCommitmentRequest,
    CompleteTaskRequest,
    ParkTaskRequest,
    PlaceWeekRequest,
    PlaceWeekTask,
    PlanDayRequest,
    QueryRequest,
    ReconcileRequest,
)
from zasky.domain.service import DomainService
from zasky.storage.database import Database
from zasky.storage.models import WeekTask
from zasky.storage.repositories import OwnerConfigRepository

AVAILABILITY = (
    '{"monday": [{"start": "09:00", "end": "17:00"}], '
    '"tuesday": [{"start": "09:00", "end": "17:00"}], '
    '"wednesday": [{"start": "09:00", "end": "17:00"}], '
    '"thursday": [{"start": "09:00", "end": "17:00"}], '
    '"friday": [{"start": "09:00", "end": "17:00"}]}'
)


@pytest.fixture
def planning_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "timezone": "Africa/Lagos",
            "weekly_availability_json": AVAILABILITY,
            "week_start_day": "monday",
            "capacity_pct": 65,
            "morning_prep_min": 30,
            "commute_buffer_min": 0,
            "transition_buffer_min": 10,
        }
    )


@pytest_asyncio.fixture
async def domain_env(tmp_path, planning_settings: Settings):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'domain.db'}"
    db = Database(database_url)
    await db.init()
    await OwnerConfigRepository(db).ensure_seeded(planning_settings)
    service = DomainService(db, planning_settings)
    try:
        yield db, service, planning_settings
    finally:
        await db.close(close_connections=False)
        await asyncio.sleep(0.2)


async def approve(service: DomainService, result: dict) -> dict:
    return await service.resolve_proposal(
        action="approve",
        code=result["proposal"],
        actor_id=OWNER_ID,
        room_id=ROOM_ID,
    )


async def create_goal(service: DomainService, year: int = 2027, title: str = "Ship Zasky") -> dict:
    return await service.propose_record(
        AddCommitmentRequest(
            operation="create",
            entry_type="year_goal",
            title=title,
            year=year,
            evidence_of_done="A dated review note and a passing demo",
        )
    )


async def create_commitment(
    service: DomainService,
    *,
    goal_id: str,
    title: str = "Ship the planning loop",
    estimate: int = 600,
) -> dict:
    return await service.propose_record(
        AddCommitmentRequest(
            operation="create",
            entry_type="month_commitment",
            title=title,
            year=2027,
            month=1,
            goal_id=goal_id,
            est_min=estimate,
            deadline_local_date=date(2027, 1, 31),
            consequence="Misses the launch window",
            priority="high",
        )
    )


async def create_week(
    service: DomainService,
    commitment_id: str,
    *,
    week_start: date = date(2026, 11, 2),
    tasks: list[PlaceWeekTask] | None = None,
) -> dict:
    return await service.propose_week(
        PlaceWeekRequest(
            week_start=week_start,
            tasks=tasks
            or [
                PlaceWeekTask(
                    commitment_id=commitment_id,
                    task_title="Draft the recovery proposal",
                    est_min=90,
                    scheduled_date=date(2026, 11, 6),
                ),
                PlaceWeekTask(
                    commitment_id=commitment_id,
                    task_title="Review the week arithmetic",
                    est_min=30,
                    scheduled_date=date(2026, 11, 6),
                ),
            ],
        )
    )


@pytest.mark.asyncio
async def test_goal_create_and_approval(domain_env) -> None:
    _db, service, _settings = domain_env
    result = await create_goal(service)
    assert result["proposal"].startswith("ZK-")
    approved = await approve(service, result)
    assert approved["status"] == "approved"
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    assert goals["goals"][0]["title"] == "Ship Zasky"


@pytest.mark.asyncio
async def test_five_active_goals_is_the_limit(domain_env) -> None:
    _db, service, _settings = domain_env
    for index in range(5):
        result = await create_goal(service, title=f"Goal {index}")
        await approve(service, result)
    with pytest.raises(DomainError) as exc:
        await create_goal(service, title="Goal 6")
    assert exc.value.code == "CONFLICT"


@pytest.mark.asyncio
async def test_goal_requires_evidence(domain_env) -> None:
    _db, service, _settings = domain_env
    with pytest.raises(ValidationError):
        AddCommitmentRequest(
            operation="create",
            entry_type="year_goal",
            title="No evidence",
            year=2027,
        )


@pytest.mark.asyncio
async def test_week_placement_approval_and_capacity(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    commitment_id = commitments["commitments"][0]["id"]
    week = await create_week(service, commitment_id)
    approved = await approve(service, week)
    assert approved["status"] == "approved"
    week_state = await service.query(QueryRequest(state="week", horizon="2026-11-02"))
    assert len(week_state["tasks"]) == 2
    assert week_state["capacity"]["budget_min"] > 0


@pytest.mark.asyncio
async def test_ad_hoc_requires_explicit_flag(domain_env) -> None:
    _db, service, _settings = domain_env
    with pytest.raises(DomainError) as exc:
        await service.propose_week(
            PlaceWeekRequest(
                week_start=date(2026, 11, 2),
                tasks=[
                    PlaceWeekTask(
                        task_title="Unowned task",
                        est_min=30,
                        scheduled_date=date(2026, 11, 6),
                    )
                ],
            )
        )
    assert exc.value.code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_task_date_outside_week_is_rejected(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    with pytest.raises(DomainError) as exc:
        await create_week(
            service,
            commitments["commitments"][0]["id"],
            tasks=[
                PlaceWeekTask(
                    commitment_id=commitments["commitments"][0]["id"],
                    task_title="Outside",
                    est_min=30,
                    scheduled_date=date(2026, 11, 9),
                )
            ],
        )
    assert exc.value.code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_plan_day_one_must_and_backplan(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="medium")
    )
    items = plan["payload"]["items"]
    assert len(items) == 2
    assert items[0]["disposition"] == "must"
    assert all(item["disposition"] in {"must", "should"} for item in items)
    assert plan["payload"]["latest_wake_utc"].endswith("+00:00")
    await approve(service, plan)
    state = await service.query(QueryRequest(state="today", horizon="2026-11-06"))
    assert len(state["items"]) == 2


@pytest.mark.asyncio
async def test_low_battery_limits_should_task(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="low")
    )
    items = plan["payload"]["items"]
    assert len(items) == 2
    assert items[0]["disposition"] == "must"
    assert items[1]["disposition"] == "should"


@pytest.mark.asyncio
async def test_low_battery_plan_reports_remaining_week_pool(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(
        service, goal_id=goals["goals"][0]["id"]
    )
    await approve(service, commitment)
    commitments = await service.query(
        QueryRequest(state="month", horizon="2027-01")
    )
    commitment_id = commitments["commitments"][0]["id"]
    tasks = [
        PlaceWeekTask(
            commitment_id=commitment_id,
            task_title=f"Week pool task {index}",
            est_min=15,
            scheduled_date=date(2026, 11, 6),
        )
        for index in range(11)
    ]
    week = await create_week(service, commitment_id, tasks=tasks)
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="low")
    )
    payload = plan["payload"]
    assert len(payload["items"]) == 2
    assert payload["week_pool_active_count"] == 11
    assert payload["not_selected_count"] == 9
    assert payload["selected_est_min_total"] == 30
    assert payload["task_cap"] == 2


@pytest.mark.asyncio
async def test_override_schedules_all_day_tasks_and_warns(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(
        service, goal_id=goals["goals"][0]["id"]
    )
    await approve(service, commitment)
    commitments = await service.query(
        QueryRequest(state="month", horizon="2027-01")
    )
    commitment_id = commitments["commitments"][0]["id"]
    tasks = [
        PlaceWeekTask(
            commitment_id=commitment_id,
            task_title=f"Override task {index}",
            est_min=15,
            scheduled_date=date(2026, 11, 6),
        )
        for index in range(11)
    ]
    week = await create_week(service, commitment_id, tasks=tasks)
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(
            date=date(2026, 11, 6),
            battery="medium",
            override_limits=True,
        )
    )
    payload = plan["payload"]
    assert payload["override_limits"] is True
    assert len(payload["items"]) == 11
    assert (
        sum(
            1
            for item in payload["items"]
            if item["disposition"] == "must"
        )
        == 1
    )
    assert payload["not_selected_count"] == 0
    assert payload["unplaced_count"] == 0
    assert payload["selected_est_min_total"] == 165
    assert payload["daily_available_min"] == 480


@pytest.mark.asyncio
async def test_park_requires_note_and_complete_is_idempotent(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    week_state = await service.query(QueryRequest(state="week", horizon="2026-11-02"))
    task_id = week_state["tasks"][0]["id"]

    with pytest.raises(ValidationError):
        ParkTaskRequest(task_id=task_id, action="park")
    parked = await service.park_task(
        ParkTaskRequest(
            task_id=task_id,
            action="park",
            resume_note="Stopped after the outline; next: write the opening section.",
        )
    )
    assert parked["status"] == "parked"
    resumed = await service.park_task(
        ParkTaskRequest(task_id=task_id, action="resume")
    )
    assert resumed["status"] == "active"
    completed = await service.complete_task(
        CompleteTaskRequest(task_id=task_id, actual_min=45)
    )
    assert completed["status"] == "completed"
    again = await service.complete_task(CompleteTaskRequest(task_id=task_id))
    assert again["already"] == "completed"


@pytest.mark.asyncio
async def test_reject_does_not_mutate(domain_env) -> None:
    _db, service, _settings = domain_env
    result = await create_goal(service)
    rejected = await service.resolve_proposal(
        action="reject",
        code=result["proposal"],
        actor_id=OWNER_ID,
        room_id=ROOM_ID,
    )
    assert rejected["status"] == "rejected"
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    assert goals["goals"] == []
    with pytest.raises(DomainError) as exc:
        await approve(service, result)
    assert exc.value.code == "CONFLICT"


@pytest.mark.asyncio
async def test_approval_parser_is_exact() -> None:
    from zasky.access.approvals import parse_approval_command

    assert parse_approval_command("approve ZK-4F8Q").code == "ZK-4F8Q"
    assert parse_approval_command("looks good") is None
    assert parse_approval_command("yes") is None
    assert parse_approval_command("approve").code is None


@pytest.mark.asyncio
async def test_reconcile_proposal_reports_feasibility(domain_env) -> None:
    _db, service, settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="high")
    )
    await approve(service, plan)
    tz = ZoneInfo(settings.timezone)
    now = datetime(2026, 11, 6, 16, 0, tzinfo=tz)
    reconcile = await service.propose_reconcile(
        ReconcileRequest(
            what_happened="A call ran two hours over; I am back now.",
            now_iso=now,
        )
    )
    assert reconcile["payload"]["feasibility"]["status"] in {
        "week_holds",
        "week_at_risk",
        "insufficient_data",
    }
    assert "arithmetic" in reconcile["payload"]["feasibility"]
    approved = await approve(service, reconcile)
    assert approved["status"] == "approved"


@pytest.mark.asyncio
async def test_stale_day_proposal_is_not_applied(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="medium")
    )
    task_id = plan["payload"]["items"][0]["task_id"]
    await service.park_task(
        ParkTaskRequest(
            task_id=task_id,
            action="park",
            resume_note="Next: finish the opening section.",
        )
    )
    with pytest.raises(DomainError) as exc:
        await approve(service, plan)
    assert exc.value.code == "PROPOSAL_STALE"


@pytest.mark.asyncio
async def test_expired_proposal_is_not_applied(domain_env) -> None:
    db, service, _settings = domain_env
    result = await create_goal(service)
    from zasky.storage.models import PendingProposal

    async with db.locked_session() as session:
        proposal = await session.scalar(
            select(PendingProposal).where(PendingProposal.code == result["proposal"])
        )
        assert proposal is not None
        proposal.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
    with pytest.raises(DomainError) as exc:
        await approve(service, result)
    assert exc.value.code == "PROPOSAL_EXPIRED"


@pytest.mark.asyncio
async def test_daily_capacity_is_enforced(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    with pytest.raises(DomainError) as exc:
        await create_week(
            service,
            commitments["commitments"][0]["id"],
            tasks=[
                PlaceWeekTask(
                    commitment_id=commitments["commitments"][0]["id"],
                    task_title="First large block",
                    est_min=300,
                    scheduled_date=date(2026, 11, 6),
                ),
                PlaceWeekTask(
                    commitment_id=commitments["commitments"][0]["id"],
                    task_title="Second large block",
                    est_min=300,
                    scheduled_date=date(2026, 11, 6),
                ),
            ],
        )
    assert exc.value.code == "CAPACITY_EXCEEDED"


@pytest.mark.asyncio
async def test_plan_day_never_selects_more_than_three(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    tasks = [
        PlaceWeekTask(
            commitment_id=commitments["commitments"][0]["id"],
            task_title=f"Small block {index}",
            est_min=30,
            scheduled_date=date(2026, 11, 6),
        )
        for index in range(4)
    ]
    week = await create_week(
        service, commitments["commitments"][0]["id"], tasks=tasks
    )
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="high")
    )
    assert len(plan["payload"]["items"]) == 3
    assert sum(1 for item in plan["payload"]["items"] if item["disposition"] == "must") == 1


@pytest.mark.asyncio
async def test_parked_task_is_excluded_from_day_plan(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    week_state = await service.query(QueryRequest(state="week", horizon="2026-11-02"))
    parked_id = week_state["tasks"][0]["id"]
    await service.park_task(
        ParkTaskRequest(
            task_id=parked_id,
            action="park",
            resume_note="Next: continue tomorrow.",
        )
    )
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="high")
    )
    assert parked_id not in [item["task_id"] for item in plan["payload"]["items"]]


@pytest.mark.asyncio
async def test_fixed_event_pushes_work_and_backplan(domain_env) -> None:
    _db, service, settings = domain_env
    event = await service.propose_record(
        AddCommitmentRequest(
            operation="create",
            entry_type="fixed_event",
            title="Standup",
            starts_at=datetime(2026, 11, 6, 9, 0, tzinfo=ZoneInfo(settings.timezone)),
            ends_at=datetime(2026, 11, 6, 11, 0, tzinfo=ZoneInfo(settings.timezone)),
        )
    )
    await approve(service, event)
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    plan = await service.propose_day(
        PlanDayRequest(date=date(2026, 11, 6), battery="medium")
    )
    first_start = datetime.fromisoformat(plan["payload"]["items"][0]["planned_start_utc"])
    assert first_start.astimezone(ZoneInfo(settings.timezone)).hour >= 11
    latest = datetime.fromisoformat(plan["payload"]["latest_wake_utc"])
    assert latest.astimezone(ZoneInfo(settings.timezone)).strftime("%H:%M") == "08:30"


@pytest.mark.asyncio
async def test_commitment_cancellation_cancels_tasks(domain_env) -> None:
    db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    commitment_id = commitments["commitments"][0]["id"]
    week = await create_week(service, commitment_id)
    await approve(service, week)
    update = await service.propose_record(
        AddCommitmentRequest(
            operation="update",
            entry_type="month_commitment",
            entity_id=commitment_id,
            title="Ship the planning loop",
            status="cancelled",
        )
    )
    await approve(service, update)
    async with db.locked_session() as session:
        tasks = (
            await session.execute(select(WeekTask).where(WeekTask.id.is_not(None)))
        ).scalars().all()
        assert tasks
        assert all(task.status == "cancelled" for task in tasks)


@pytest.mark.asyncio
async def test_approval_without_code_requires_exactly_one_pending(domain_env) -> None:
    _db, service, _settings = domain_env
    first = await create_goal(service, title="First")
    await create_goal(service, title="Second")
    with pytest.raises(DomainError) as exc:
        await service.resolve_proposal(
            action="approve", code=None, actor_id=OWNER_ID, room_id=ROOM_ID
        )
    assert exc.value.code == "PROPOSAL_NOT_FOUND"
    approved = await service.resolve_proposal(
        action="approve",
        code=first["proposal"],
        actor_id=OWNER_ID,
        room_id=ROOM_ID,
    )
    assert approved["status"] == "approved"
    again = await service.resolve_proposal(
        action="approve",
        code=first["proposal"],
        actor_id=OWNER_ID,
        room_id=ROOM_ID,
    )
    assert again["already"] == "approved"


@pytest.mark.asyncio
async def test_deadline_query_marks_large_work_at_risk(domain_env) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(
        service, goal_id=goals["goals"][0]["id"], estimate=100000
    )
    await approve(service, commitment)
    deadlines = await service.query(QueryRequest(state="deadlines"))
    assert deadlines["deadlines"][0]["status"] == "at_risk"


def test_extra_tool_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AddCommitmentRequest(
            operation="create",
            entry_type="year_goal",
            title="Extra",
            year=2027,
            evidence_of_done="Done",
            unexpected="field",
        )


@pytest.mark.asyncio
async def test_plan_day_empty_pool_is_explicit(domain_env) -> None:
    _db, service, _settings = domain_env
    with pytest.raises(DomainError) as exc:
        await service.propose_day(
            PlanDayRequest(date=date(2026, 11, 6), battery="medium")
        )
    assert exc.value.code == "NO_WEEK_TASKS"


@pytest.mark.asyncio
async def test_fixed_event_cannot_be_moved(domain_env) -> None:
    _db, service, settings = domain_env
    event = await service.propose_record(
        AddCommitmentRequest(
            operation="create",
            entry_type="fixed_event",
            title="Standup",
            starts_at=datetime(2026, 11, 6, 9, 0, tzinfo=ZoneInfo(settings.timezone)),
            ends_at=datetime(2026, 11, 6, 10, 0, tzinfo=ZoneInfo(settings.timezone)),
        )
    )
    await approve(service, event)
    created = await service.query(QueryRequest(state="status"))
    # Fetch the event through a direct session rather than exposing it in a query.
    from zasky.storage.models import FixedEvent

    async with _db.locked_session() as session:
        stored = (await session.execute(select(FixedEvent))).scalars().first()
        assert stored is not None
        event_id = stored.id
    with pytest.raises(DomainError) as exc:
        await service.propose_record(
            AddCommitmentRequest(
                operation="update",
                entry_type="fixed_event",
                entity_id=event_id,
                title="Moved standup",
                starts_at=datetime(
                    2026, 11, 6, 12, 0, tzinfo=ZoneInfo(settings.timezone)
                ),
            )
        )
    assert exc.value.code == "INVALID_INPUT"
    assert created["state"] == "status"


@pytest.mark.asyncio
async def test_reconcile_cannot_cross_the_week(domain_env) -> None:
    _db, service, settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(service, goal_id=goals["goals"][0]["id"])
    await approve(service, commitment)
    commitments = await service.query(QueryRequest(state="month", horizon="2027-01"))
    week = await create_week(service, commitments["commitments"][0]["id"])
    await approve(service, week)
    tz = ZoneInfo(settings.timezone)
    with pytest.raises(DomainError) as exc:
        await service.propose_reconcile(
            ReconcileRequest(
                what_happened="I lost the week.",
                now_iso=datetime(2026, 11, 6, 16, 0, tzinfo=tz),
                to_date=date(2026, 11, 9),
            )
        )
    assert exc.value.code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_concurrent_approval_applies_once(domain_env) -> None:
    _db, service, _settings = domain_env
    result = await create_goal(service)
    first, second = await asyncio.gather(
        approve(service, result),
        approve(service, result),
        return_exceptions=True,
    )
    statuses = []
    for item in (first, second):
        if isinstance(item, DomainError):
            statuses.append(item.code)
        elif isinstance(item, Exception):
            statuses.append(type(item).__name__)
        else:
            statuses.append(item.get("status") or item.get("already"))
    assert "approved" in statuses
    assert any(
        (isinstance(item, dict) and item.get("already") == "approved")
        for item in (first, second)
    )
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    assert len(goals["goals"]) == 1


@pytest.mark.asyncio
async def test_dashboard_task_appends_to_existing_commitment_placement(
    domain_env,
) -> None:
    _db, service, _settings = domain_env
    goal = await create_goal(service)
    await approve(service, goal)
    goals = await service.query(QueryRequest(state="goals", horizon="2027"))
    commitment = await create_commitment(
        service, goal_id=goals["goals"][0]["id"]
    )
    await approve(service, commitment)
    commitments = await service.query(
        QueryRequest(state="month", horizon="2027-01")
    )
    commitment_id = commitments["commitments"][0]["id"]
    week = await create_week(service, commitment_id)
    await approve(service, week)

    task = await service.add_week_task(
        title="Add the dashboard task",
        est_min=20,
        week_start=date(2026, 11, 2),
        scheduled_date=date(2026, 11, 6),
        commitment_id=commitment_id,
    )
    assert task["title"] == "Add the dashboard task"
    assert task["ad_hoc"] is False

    week_state = await service.query(
        QueryRequest(state="week", horizon="2026-11-02")
    )
    assert len(week_state["tasks"]) == 3
    detail = await service.task_detail(task["id"])
    assert detail["commitment_title"] == "Ship the planning loop"
    assert detail["commitment_priority"] == "high"
    assert detail["commitment_deadline"] == "2027-01-31"
    assert detail["goal_title"] == "Ship Zasky"
    assert detail["goal_evidence_of_done"] == (
        "A dated review note and a passing demo"
    )
    assert detail["scheduled_date"] == "2026-11-06"


@pytest.mark.asyncio
async def test_dashboard_ad_hoc_task_uses_week_pool(domain_env) -> None:
    _db, service, _settings = domain_env
    task = await service.add_week_task(
        title="Dashboard ad hoc task",
        est_min=15,
        week_start=date(2026, 11, 2),
        scheduled_date=date(2026, 11, 6),
    )
    assert task["ad_hoc"] is True
    assert task["status"] == "active"
    detail = await service.task_detail(task["id"])
    assert detail["commitment_title"] is None


@pytest.mark.asyncio
async def test_task_execution_type_defaults_human_and_accepts_ai(domain_env) -> None:
    _db, service, _settings = domain_env
    human = await service.add_week_task(
        title="Call the dentist",
        est_min=15,
        week_start=date(2026, 11, 2),
        scheduled_date=date(2026, 11, 6),
    )
    ai = await service.add_week_task(
        title="Draft a launch email",
        est_min=20,
        week_start=date(2026, 11, 2),
        scheduled_date=date(2026, 11, 6),
        execution_type="ai",
    )
    assert human["execution_type"] == "human"
    assert ai["execution_type"] == "ai"
    with pytest.raises(DomainError) as excinfo:
        await service.add_week_task(
            title="Invalid type",
            est_min=10,
            week_start=date(2026, 11, 2),
            scheduled_date=date(2026, 11, 6),
            execution_type="robot",
        )
    assert excinfo.value.code == "INVALID_INPUT"
