from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from zasky.agent.briefing import BriefingBuilder
from zasky.config import Settings
from zasky.scheduler.alarms import AlarmScheduler
from zasky.storage.database import Database
from zasky.storage.models import (
    AlarmDispatch,
    DayPlan,
    DayPlanItem,
    FixedEvent,
    WeekPlacement,
    WeekTask,
)
from zasky.storage.repositories import OwnerConfigRepository


class FakeOps:
    def __init__(self) -> None:
        self.posts: list[tuple[str, str | None]] = []

    async def post_message(self, body: str, *, thread_id: str | None = None) -> dict:
        self.posts.append((body, thread_id))
        return {"event_id": "posted"}


async def seed_plan(db: Database, *, start_utc: datetime) -> tuple[str, str]:
    async with db.locked_session() as session:
        placement = WeekPlacement(
            id="placement-1",
            commitment_id=None,
            source_type="ad_hoc",
            week_start=date(2026, 11, 2),
            status="active",
            revision=1,
        )
        task = WeekTask(
            id="task-1",
            placement_id=placement.id,
            title="Record the demo narration",
            est_min=45,
            scheduled_date=date(2026, 11, 6),
            status="active",
            ad_hoc=True,
            execution_type="ai",
        )
        plan = DayPlan(
            id="plan-1",
            local_date=date(2026, 11, 6),
            revision=1,
            battery="medium",
            status="approved",
            source="plan_day",
            latest_wake_utc=datetime(2026, 11, 6, 7, 30, tzinfo=UTC),
        )
        item = DayPlanItem(
            id="item-1",
            day_plan_id=plan.id,
            task_id=task.id,
            position=1,
            disposition="must",
            planned_start_utc=start_utc,
            planned_end_utc=start_utc + timedelta(minutes=45),
            planned_est_min=45,
            outcome="pending",
        )
        session.add(placement)
        await session.flush()
        session.add(task)
        await session.flush()
        session.add(plan)
        await session.flush()
        session.add(
            FixedEvent(
                id="event-1",
                title="Synthetic family dinner",
                starts_at_utc=datetime(2026, 11, 6, 17, 0, tzinfo=UTC),
                ends_at_utc=datetime(2026, 11, 6, 18, 30, tzinfo=UTC),
                status="active",
                source="owner",
            )
        )
        session.add(item)
        await session.commit()
    return plan.id, item.id


@pytest.mark.asyncio
async def test_alarm_sends_once_at_task_start(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'alarm.db'}")
    await db.init()
    ops = FakeOps()
    start = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)  # 09:00 Africa/Lagos
    try:
        plan_id, item_id = await seed_plan(db, start_utc=start)
        scheduler = AlarmScheduler(db, ops, settings)  # type: ignore[arg-type]
        sent = await scheduler.tick(now=start + timedelta(seconds=10))
        assert sent == 1
        assert len(ops.posts) == 1
        body, thread_id = ops.posts[0]
        assert "⏰ **Timebox Started:**" in body
        assert "It's 09:00 AM" in body
        assert "You planned 45 min for **Record the demo narration**" in body
        assert "Reply with 'done' or 'park' when finished." in body
        assert thread_id is None

        sent_again = await scheduler.tick(now=start + timedelta(seconds=20))
        assert sent_again == 0
        assert len(ops.posts) == 1

        async with db.locked_session() as session:
            rows = (await session.execute(select(AlarmDispatch))).scalars().all()
            assert len(rows) == 1
            assert rows[0].status == "sent"
            assert rows[0].day_plan_item_id == item_id
            assert rows[0].task_id == "task-1"
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_alarm_skips_outside_grace(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'alarm.db'}")
    await db.init()
    ops = FakeOps()
    start = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    try:
        await seed_plan(db, start_utc=start)
        scheduler = AlarmScheduler(db, ops, settings, grace_minutes=5)  # type: ignore[arg-type]
        sent = await scheduler.tick(now=start + timedelta(minutes=10))
        assert sent == 0
        assert ops.posts == []
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_briefing_is_formatted_and_has_fixed_events(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'brief.db'}")
    await db.init()
    start = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    try:
        await seed_plan(db, start_utc=start)
        briefing = await BriefingBuilder(db, settings).build(date(2026, 11, 6))
        assert "📅 **Daily Briefing — Friday, Nov 6**" in briefing
        assert "**MUST DO:**" in briefing
        assert "📌 **Record the demo narration** — 09:00 AM–09:45 AM" in briefing
        assert "**FIXED:**" in briefing
        assert "📍 **Synthetic family dinner** — 06:00 PM–07:30 PM" in briefing
        assert "⏰ **Latest Wake:** 08:30 AM" in briefing
        assert "📅 **Add to Google Calendar:**" in briefing
        assert "calendar.google.com/calendar/render" in briefing
        assert "action=TEMPLATE" in briefing
    finally:
        await db.close()
        await asyncio.sleep(0.2)


class FakeDocumentOps(FakeOps):
    def __init__(self) -> None:
        super().__init__()
        self.documents: list[dict] = []

    async def create_room_document(self, **kwargs) -> dict:
        self.documents.append(kwargs)
        return {"ok": True}


class FakeDiscord:
    def __init__(self, delivered: bool = True) -> None:
        self.delivered = delivered
        self.daily: list[tuple[str, str]] = []
        self.reconcile: list[dict] = []
        self.execution: list[dict] = []

    async def send_daily_briefing(self, briefing: str, local_date: str) -> bool:
        self.daily.append((briefing, local_date))
        return self.delivered

    async def send_reconcile_summary(self, **kwargs) -> bool:
        self.reconcile.append(kwargs)
        return self.delivered

    async def send_execution_result(self, **kwargs) -> bool:
        self.execution.append(kwargs)
        return self.delivered

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_plan_approval_briefing_posts_and_persists(tmp_path, settings: Settings) -> None:
    from zasky.app import ZaskyApp

    configured = settings.model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{tmp_path / 'app.db'}"}
    )
    app = ZaskyApp(configured)
    await app.db.init()
    await OwnerConfigRepository(app.db).ensure_seeded(configured)
    start = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    try:
        await seed_plan(app.db, start_utc=start)
        ops = FakeDocumentOps()
        discord = FakeDiscord()
        app.ops = ops  # type: ignore[assignment]
        app.discord = discord  # type: ignore[assignment]
        note = await app._post_daily_briefing("2026-11-06")
        assert "posted to `#daily-briefings`" in note
        assert ops.posts == []
        assert len(discord.daily) == 1
        assert "Daily Briefing" in discord.daily[0][0]
        assert len(ops.documents) == 1
        assert ops.documents[0]["name"] == "Daily Briefing — 2026-11-06"
    finally:
        await app.db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_daily_briefing_falls_back_when_discord_unconfigured(
    tmp_path, settings: Settings
) -> None:
    from zasky.app import ZaskyApp

    configured = settings.model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{tmp_path / 'app-fallback.db'}"}
    )
    app = ZaskyApp(configured)
    await app.db.init()
    await OwnerConfigRepository(app.db).ensure_seeded(configured)
    start = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    try:
        await seed_plan(app.db, start_utc=start)
        ops = FakeDocumentOps()
        app.ops = ops  # type: ignore[assignment]
        app.discord = FakeDiscord(delivered=False)  # type: ignore[assignment]
        note = await app._post_daily_briefing("2026-11-06")
        assert "main room" in note
        assert len(ops.posts) == 1
    finally:
        await app.db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_reconcile_summary_is_routed_to_channel(
    tmp_path, settings: Settings
) -> None:
    from zasky.app import ZaskyApp

    configured = settings.model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{tmp_path / 'app-reconcile.db'}"}
    )
    app = ZaskyApp(configured)
    await app.db.init()
    await OwnerConfigRepository(app.db).ensure_seeded(configured)
    start = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    try:
        await seed_plan(app.db, start_utc=start)
        discord = FakeDiscord()
        app.discord = discord  # type: ignore[assignment]
        note = await app._post_reconcile_summary(
            "ZK-TEST",
            {
                "date": "2026-11-06",
                "items": 1,
                "moves": 2,
                "feasibility": "week_holds",
            },
        )
        assert "#reconcile-alerts" in note
        assert len(discord.reconcile) == 1
        assert discord.reconcile[0]["code"] == "ZK-TEST"
        assert discord.reconcile[0]["moves"] == 2
        assert discord.reconcile[0]["items"][0]["title"] == "Record the demo narration"
    finally:
        await app.db.close(close_connections=False)
        await asyncio.sleep(0.2)
