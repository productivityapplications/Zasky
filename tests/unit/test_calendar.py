from __future__ import annotations

from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from tests.unit.test_scheduler import seed_plan
from zasky.config import Settings
from zasky.integrations.calendar import (
    build_calendar_feed,
    google_calendar_day_quick_add_url,
    google_calendar_quick_add_url,
)
from zasky.storage.database import Database


@pytest.mark.asyncio
async def test_calendar_feed_contains_fixed_events_and_task_alarms(
    tmp_path, settings: Settings
) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'calendar.db'}")
    await db.init()
    try:
        await seed_plan(
            db, start_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
        )
        feed = await build_calendar_feed(
            db,
            settings,
            now=datetime(2026, 11, 6, 7, 0, tzinfo=UTC),
        )
        assert feed.startswith("BEGIN:VCALENDAR\r\n")
        assert feed.endswith("END:VCALENDAR\r\n")
        assert "VERSION:2.0" in feed
        assert "X-WR-TIMEZONE:Africa/Lagos" in feed
        assert "SUMMARY:Record the demo narration" in feed
        assert "SUMMARY:Synthetic family dinner" in feed
        assert "DTSTART:20261106T080000Z" in feed
        assert "DTSTART:20261106T170000Z" in feed
        assert "BEGIN:VALARM" in feed
        assert "TRIGGER:-PT5M" in feed
        assert "ACTION:DISPLAY" in feed
        assert "CATEGORIES:Zasky,Task" in feed
        task_events = feed.count("BEGIN:VEVENT")
        assert task_events == 2
    finally:
        await db.close(close_connections=False)


@pytest.mark.asyncio
async def test_calendar_feed_respects_alarm_setting(
    tmp_path, settings: Settings
) -> None:
    configured = settings.model_copy(update={"calendar_alarm_minutes": 15})
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'calendar-alarm.db'}")
    await db.init()
    try:
        await seed_plan(
            db, start_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
        )
        feed = await build_calendar_feed(db, configured)
        assert "TRIGGER:-PT15M" in feed
    finally:
        await db.close(close_connections=False)


def test_google_calendar_task_url() -> None:
    url = google_calendar_quick_add_url(
        title="Draft, review; plan",
        start=datetime(2026, 11, 6, 8, 0, tzinfo=UTC),
        end=datetime(2026, 11, 6, 8, 45, tzinfo=UTC),
        details="First line\nSecond line",
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "calendar.google.com"
    assert parsed.path == "/calendar/render"
    assert query["action"] == ["TEMPLATE"]
    assert query["text"] == ["Draft, review; plan"]
    assert query["dates"] == ["20261106T080000Z/20261106T084500Z"]
    assert query["details"] == ["First line\nSecond line"]


def test_google_calendar_day_url_is_all_day() -> None:
    url = google_calendar_day_quick_add_url(
        title="Zasky Plan",
        local_date=date(2026, 11, 6),
        details="MUST: Demo\nSHOULD: Review",
    )
    query = parse_qs(urlparse(url).query)
    assert query["dates"] == ["20261106/20261107"]
    assert query["text"] == ["Zasky Plan"]
