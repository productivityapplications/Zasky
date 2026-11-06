from __future__ import annotations

import asyncio

import pytest

from zasky.config import Settings
from zasky.storage.database import Database
from zasky.storage.repositories import (
    AuditRepository,
    OwnerConfigRepository,
    ScopeRevisionRepository,
)


@pytest.mark.asyncio
async def test_owner_config_is_seeded_once(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'zasky.db'}")
    await db.init()
    try:
        repo = OwnerConfigRepository(db)
        first = await repo.ensure_seeded(settings)
        second = await repo.ensure_seeded(settings)
        assert first.id == 1
        assert second.id == 1
        assert first.owner_switch_participant_id == settings.owner_switch_participant_id
        assert first.allowed_room_id == settings.switch_room_id
        assert first.timezone == settings.timezone
        assert first.capacity_pct == 65
        assert first.daily_task_limit == 3
        assert first.revision == 1
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_scope_revisions_increment(tmp_path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'zasky.db'}")
    await db.init()
    try:
        repo = ScopeRevisionRepository(db)
        assert await repo.get_or_create("week:2026-11-02") == 1
        assert await repo.get_or_create("week:2026-11-02") == 1
        assert await repo.increment("week:2026-11-02") == 2
        assert await repo.all_for(["week:2026-11-02"]) == {"week:2026-11-02": 2}
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_audit_record_is_redacted(tmp_path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'zasky.db'}")
    await db.init()
    try:
        repo = AuditRepository(db)
        event_id = await repo.record(
            actor_type="system",
            actor_id=None,
            action="day_plan_approved",
            entity_type="day_plan",
            entity_id="plan-1",
            summary_redacted="approved day plan; 2 items",
            correlation_id="corr-1",
        )
        async with db.locked_session() as session:
            from zasky.storage.models import AuditEvent

            row = await session.get(AuditEvent, event_id)
            assert row is not None
            assert row.summary_redacted == "approved day plan; 2 items"
            assert "task title" not in row.summary_redacted
    finally:
        await db.close()
        await asyncio.sleep(0.2)
