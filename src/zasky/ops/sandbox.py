"""Isolated SQLite sandbox for hackathon judges."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from zasky.config import Settings
from zasky.domain.delegation import DelegationService
from zasky.domain.errors import DomainError
from zasky.domain.schemas import (
    AddCommitmentRequest,
    PlaceWeekRequest,
    PlaceWeekTask,
    PlanDayRequest,
    QueryRequest,
)
from zasky.domain.service import DomainService
from zasky.storage.database import Database
from zasky.storage.repositories import OwnerConfigRepository

logger = logging.getLogger(__name__)


@dataclass
class SandboxScope:
    db: Database
    domain: DomainService
    delegations: DelegationService
    settings: Settings
    owner_id: str
    room_id: str
    is_sandbox: bool = True


async def build_sandbox_scope(settings: Settings) -> SandboxScope:
    if not settings.sandbox_database_url:
        raise RuntimeError("Sandbox database is not configured.")
    room_id = settings.sandbox_switch_room_id or "sandbox-room"
    sandbox_settings = settings.model_copy(
        update={
            "database_url": settings.sandbox_database_url,
            "owner_switch_participant_id": (
                settings.sandbox_owner_switch_participant_id
            ),
            "switch_room_id": room_id,
        }
    )
    db = Database(settings.sandbox_database_url)
    await db.init()
    await OwnerConfigRepository(db).ensure_seeded(sandbox_settings)
    domain = DomainService(db, sandbox_settings)
    delegations = DelegationService(db, sandbox_settings)
    await _seed_demo(domain, sandbox_settings)
    return SandboxScope(
        db=db,
        domain=domain,
        delegations=delegations,
        settings=sandbox_settings,
        owner_id=sandbox_settings.owner_switch_participant_id,
        room_id=room_id,
    )


async def _seed_demo(domain: DomainService, settings: Settings) -> None:
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(UTC).astimezone(tz).date()
    try:
        goals = await domain.query(
            QueryRequest(state="goals", horizon=str(today.year))
        )
        if goals.get("goals"):
            return
        actor = settings.owner_switch_participant_id
        room = settings.switch_room_id
        goal = await domain.propose_record(
            AddCommitmentRequest(
                operation="create",
                entry_type="year_goal",
                title="Try the Zasky judge demo",
                year=today.year,
                evidence_of_done=(
                    "A judge adds a task, completes one, and delegates one "
                    "AI task."
                ),
            )
        )
        await domain.resolve_proposal(
            action="approve",
            code=goal["proposal"],
            actor_id=actor,
            room_id=room,
        )
        goal_rows = await domain.query(
            QueryRequest(state="goals", horizon=str(today.year))
        )
        goal_id = goal_rows["goals"][0]["id"]
        commitment = await domain.propose_record(
            AddCommitmentRequest(
                operation="create",
                entry_type="month_commitment",
                title="Explore the planning loop",
                year=today.year,
                month=today.month,
                goal_id=goal_id,
                est_min=120,
                deadline_local_date=today + timedelta(days=7),
                consequence="The demo feels empty.",
                priority="high",
            )
        )
        await domain.resolve_proposal(
            action="approve",
            code=commitment["proposal"],
            actor_id=actor,
            room_id=room,
        )
        commitments = await domain.query(
            QueryRequest(
                state="month", horizon=f"{today.year}-{today.month:02d}"
            )
        )
        commitment_id = commitments["commitments"][0]["id"]
        week_start = today - timedelta(days=today.weekday())
        week = await domain.propose_week(
            PlaceWeekRequest(
                week_start=week_start,
                tasks=[
                    PlaceWeekTask(
                        commitment_id=commitment_id,
                        task_title="Draft a friendly launch email",
                        est_min=20,
                        scheduled_date=today,
                        execution_type="ai",
                    ),
                    PlaceWeekTask(
                        commitment_id=commitment_id,
                        task_title="Call the dentist",
                        est_min=15,
                        scheduled_date=today,
                        execution_type="human",
                    ),
                    PlaceWeekTask(
                        commitment_id=commitment_id,
                        task_title="Outline a 60-second product demo",
                        est_min=30,
                        scheduled_date=today,
                        execution_type="ai",
                    ),
                ],
            )
        )
        await domain.resolve_proposal(
            action="approve",
            code=week["proposal"],
            actor_id=actor,
            room_id=room,
        )
        day = await domain.propose_day(
            PlanDayRequest(date=today, battery="high")
        )
        await domain.resolve_proposal(
            action="approve",
            code=day["proposal"],
            actor_id=actor,
            room_id=room,
        )
        logger.info(
            "Sandbox demo data seeded",
            extra={"component": "sandbox"},
        )
    except DomainError as exc:
        logger.warning(
            "Sandbox demo seed skipped",
            extra={
                "component": "sandbox",
                "error_code": exc.code,
            },
        )
    except Exception:
        logger.exception(
            "Sandbox demo seed failed",
            extra={"component": "sandbox"},
        )
