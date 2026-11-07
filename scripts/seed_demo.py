"""Seed a deterministic synthetic demo plan.

This script never invents real personal data. It creates the same synthetic
goals, commitments, fixed events, week tasks and Friday day plan used by the
local transcript demo. Use `--database-url` to target an isolated demo DB.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

from zasky.config import load_settings
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

OWNER = "@owner:demo"
ROOM = "room-demo"
DEMO_WEEK = date(2026, 11, 2)
DEMO_FRIDAY = date(2026, 11, 6)


async def approve(service: DomainService, result: dict) -> dict:
    return await service.resolve_proposal(
        action="approve",
        code=result["proposal"],
        actor_id=OWNER,
        room_id=ROOM,
    )


async def seed(settings, database_url: str | None, reset: bool) -> None:
    if database_url:
        settings = settings.model_copy(update={"database_url": database_url})
    db = Database(settings.database_url)
    if reset:
        path = make_url(settings.database_url).database
        if path and path != ":memory:":
            for suffix in ("", "-wal", "-shm"):
                await asyncio.to_thread(
                    Path(str(path) + suffix).unlink, missing_ok=True
                )
    await db.init()
    await OwnerConfigRepository(db).ensure_seeded(settings)
    service = DomainService(db, settings)
    try:
        existing = await service.query(QueryRequest(state="goals", horizon="2026"))
        if existing["goals"]:
            print("demo plan already seeded; leaving it unchanged")
            return

        for title, evidence in [
            (
                "Deliver the Zasky hackathon demo",
                "Reviewed a 150-second local transcript demo and committed release notes.",
            ),
            (
                "Keep a calm weekly planning rhythm",
                "Four weekly reviews recorded with one must completed each week.",
            ),
            (
                "Publish the operator handoff",
                "README, setup notes and deployment boundaries reviewed by the operator.",
            ),
        ]:
            result = await service.propose_record(
                AddCommitmentRequest(
                    operation="create",
                    entry_type="year_goal",
                    title=title,
                    year=2026,
                    evidence_of_done=evidence,
                )
            )
            await approve(service, result)
        goal_rows = await service.query(QueryRequest(state="goals", horizon="2026"))
        goal_ids = [row["id"] for row in goal_rows["goals"]]

        commitments = {}
        for title, estimate, deadline, consequence, priority, goal_id in [
            (
                "Produce the Zasky demo package",
                600,
                date(2026, 11, 8),
                "Hackathon submission is incomplete.",
                "high",
                goal_ids[0],
            ),
            (
                "Finish the release checklist",
                240,
                date(2026, 11, 7),
                "Release status is unverified.",
                "high",
                goal_ids[0],
            ),
            (
                "Write the operator handoff",
                180,
                date(2026, 11, 8),
                "The operator cannot reproduce setup.",
                "normal",
                goal_ids[2] if len(goal_ids) > 2 else None,
            ),
        ]:
            result = await service.propose_record(
                AddCommitmentRequest(
                    operation="create",
                    entry_type="month_commitment",
                    title=title,
                    year=2026,
                    month=11,
                    goal_id=goal_id,
                    est_min=estimate,
                    deadline_local_date=deadline,
                    consequence=consequence,
                    priority=priority,
                )
            )
            await approve(service, result)
        commitment_rows = await service.query(
            QueryRequest(state="month", horizon="2026-11")
        )
        for row in commitment_rows["commitments"]:
            commitments[row["title"]] = row["id"]

        tz = ZoneInfo(settings.timezone)
        for title, start, end in [
            (
                "Synthetic standup",
                datetime(2026, 11, 2, 9, 0, tzinfo=tz),
                datetime(2026, 11, 2, 9, 30, tzinfo=tz),
            ),
            (
                "Synthetic design review",
                datetime(2026, 11, 4, 14, 0, tzinfo=tz),
                datetime(2026, 11, 4, 15, 0, tzinfo=tz),
            ),
            (
                "Synthetic family dinner",
                datetime(2026, 11, 6, 18, 0, tzinfo=tz),
                datetime(2026, 11, 6, 19, 30, tzinfo=tz),
            ),
        ]:
            result = await service.propose_record(
                AddCommitmentRequest(
                    operation="create",
                    entry_type="fixed_event",
                    title=title,
                    starts_at=start,
                    ends_at=end,
                )
            )
            await approve(service, result)

        week_tasks = [
            (
                "Write the demo script",
                45,
                date(2026, 11, 4),
                "Produce the Zasky demo package",
                "ai",
            ),
            (
                "Record the demo narration",
                45,
                date(2026, 11, 6),
                "Produce the Zasky demo package",
                "human",
            ),
            (
                "Capture the recovery transcript",
                60,
                date(2026, 11, 6),
                "Produce the Zasky demo package",
                "human",
            ),
            (
                "Review the release checklist",
                30,
                date(2026, 11, 5),
                "Finish the release checklist",
                "ai",
            ),
            (
                "Check backup restore evidence",
                30,
                date(2026, 11, 3),
                "Finish the release checklist",
                "human",
            ),
            (
                "Draft the operator handoff",
                60,
                date(2026, 11, 5),
                "Write the operator handoff",
                "ai",
            ),
        ]
        result = await service.propose_week(
            PlaceWeekRequest(
                week_start=DEMO_WEEK,
                tasks=[
                    PlaceWeekTask(
                        commitment_id=commitments[commitment_title],
                        task_title=title,
                        est_min=estimate,
                        scheduled_date=scheduled,
                        execution_type=execution_type,
                    )
                    for title, estimate, scheduled, commitment_title, execution_type in week_tasks
                ],
            )
        )
        await approve(service, result)

        day = await service.propose_day(
            PlanDayRequest(date=DEMO_FRIDAY, battery="high")
        )
        await approve(service, day)

        print("seeded synthetic demo plan")
        week = await service.query(QueryRequest(state="week", horizon="2026-11-02"))
        print(
            f"week budget: {week['capacity']['budget_min']} min; "
            f"work: {week['remaining_work_min']} min"
        )
        print(f"friday tasks: {len(week['tasks'])} in week pool")
    finally:
        await db.close(close_connections=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="/root/Zasky-secrets/zasky.env")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    settings = load_settings(args.env_file)
    asyncio.run(seed(settings, args.database_url, args.reset))


if __name__ == "__main__":
    main()
