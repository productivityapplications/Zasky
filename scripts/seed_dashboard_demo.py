"""Seed dashboard-only synthetic demo data in an existing Zasky database.

The base demo seed creates a deterministic Friday plan. This script adds what the
owner dashboard needs for a credible live walkthrough:

* one approved plan for today with deterministic ad-hoc tasks;
* one approved reconciliation record so the recovery history is not empty.

It is idempotent and only creates synthetic data.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from zasky.config import Settings, load_settings
from zasky.domain.errors import DomainError
from zasky.domain.schemas import (
    PlaceWeekRequest,
    PlaceWeekTask,
    PlanDayRequest,
    QueryRequest,
    ReconcileRequest,
)
from zasky.domain.service import DomainService
from zasky.planner.core import week_start_for
from zasky.storage.database import Database
from zasky.storage.models import DayPlan
from zasky.storage.repositories import OwnerConfigRepository


async def approve(service: DomainService, settings: Settings, result: dict) -> dict:
    return await service.resolve_proposal(
        action="approve",
        code=result["proposal"],
        actor_id=settings.owner_switch_participant_id,
        room_id=settings.switch_room_id,
    )


async def has_reconciliation(db: Database) -> bool:
    async with db.locked_session() as session:
        existing = await session.scalar(
            select(DayPlan.id).where(DayPlan.source == "reconcile").limit(1)
        )
        return existing is not None


async def today_has_plan(service: DomainService, target: date) -> bool:
    result = await service.query(
        QueryRequest(state="today", horizon=target.isoformat())
    )
    return bool(result.get("items"))


async def seed(settings: Settings) -> None:
    db = Database(settings.database_url)
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(UTC).astimezone(tz).date()
    yesterday = today - timedelta(days=1)
    try:
        await db.init()
        await OwnerConfigRepository(db).ensure_seeded(settings)
        service = DomainService(db, settings)

        if not await has_reconciliation(db):
            yesterday_start = week_start_for(yesterday, settings.week_start_day)
            if yesterday_start != week_start_for(today, settings.week_start_day):
                yesterday = today
            now_local = datetime.combine(
                yesterday, time(14, 0), tzinfo=tz
            )
            try:
                proposal = await service.propose_reconcile(
                    ReconcileRequest(
                        what_happened=(
                            "Synthetic demo: a meeting ran long and the afternoon "
                            "needed a recovery plan."
                        ),
                        now_iso=now_local,
                        from_date=yesterday,
                    )
                )
                await approve(service, settings, proposal)
                print(f"seeded reconciliation history for {yesterday.isoformat()}")
            except DomainError as exc:
                print(f"reconciliation seed skipped: {exc.code}: {exc.message}")
        else:
            print("reconciliation history already present")

        if not await today_has_plan(service, today):
            week_start = week_start_for(today, settings.week_start_day)
            try:
                week = await service.propose_week(
                    PlaceWeekRequest(
                        week_start=week_start,
                        tasks=[
                            PlaceWeekTask(
                                task_title="Prepare the dashboard walkthrough",
                                est_min=30,
                                scheduled_date=today,
                                ad_hoc=True,
                                execution_type="ai",
                            ),
                            PlaceWeekTask(
                                task_title="Verify the Vercel proxy",
                                est_min=30,
                                scheduled_date=today,
                                ad_hoc=True,
                                execution_type="ai",
                            ),
                        ],
                    )
                )
                await approve(service, settings, week)
            except DomainError as exc:
                print(f"dashboard task seed skipped: {exc.code}: {exc.message}")

            try:
                proposal = await service.propose_day(
                    PlanDayRequest(date=today, battery="high")
                )
                await approve(service, settings, proposal)
                print(f"seeded today's plan for {today.isoformat()}")
            except DomainError as exc:
                print(f"today plan seed skipped: {exc.code}: {exc.message}")
        else:
            print(f"today's plan already present for {today.isoformat()}")

        current_week = week_start_for(today, settings.week_start_day)
        week = await service.query(
            QueryRequest(state="week", horizon=current_week.isoformat())
        )
        print(
            f"dashboard seed ready: {len(week['tasks'])} tasks in the current week pool"
        )
    finally:
        await db.close(close_connections=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="/root/Zasky-secrets/zasky.env")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    settings = load_settings(args.env_file)
    if args.database_url:
        settings = settings.model_copy(update={"database_url": args.database_url})
    asyncio.run(seed(settings))


if __name__ == "__main__":
    main()
