from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from zasky.storage.database import Database


@pytest.mark.asyncio
async def test_state_and_event_ledger_round_trip(tmp_path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.init()
    try:
        await db.save_connection_state(
            agent_id="agent-1",
            connection_id="conn-1",
            generation="7",
            protocol_revision="9",
            cursor=100,
            connected_at=datetime.now(UTC),
        )
        state = await db.get_connection_state("agent-1")
        assert state is not None
        assert state.highest_processed_sequence == 100
        assert state.generation == "7"

        claimed = await db.claim_event(
            agent_id="agent-1",
            sequence=101,
            connection_id="conn-1",
            room_id="room-1",
            sender_id="@owner:test",
            message_id="m1",
            correlation_id="corr-1",
        )
        assert claimed.is_new is True

        duplicate = await db.claim_event(
            agent_id="agent-1",
            sequence=101,
            connection_id="conn-1",
            room_id="room-1",
            sender_id="@owner:test",
            message_id="m1",
            correlation_id="corr-2",
        )
        assert duplicate.is_new is False
        assert duplicate.existing_outcome == "processing"

        await db.finish_event(
            agent_id="agent-1",
            sequence=101,
            connection_id="conn-1",
            outcome="replied",
            generation="7",
            protocol_revision="9",
        )
        assert await db.get_event_outcome("agent-1", 101) == "replied"
        state = await db.get_connection_state("agent-1")
        assert state is not None
        assert state.highest_processed_sequence == 101
        assert await db.pending_event_count("agent-1") == 0
        assert await db.healthcheck() is True
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_advance_cursor_never_moves_backwards(tmp_path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.init()
    try:
        await db.advance_cursor(
            agent_id="agent-1",
            connection_id="conn-1",
            sequence=10,
        )
        await db.advance_cursor(
            agent_id="agent-1",
            connection_id="conn-1",
            sequence=4,
        )
        state = await db.get_connection_state("agent-1")
        assert state is not None
        assert state.highest_processed_sequence == 10
    finally:
        await db.close()
        await asyncio.sleep(0.2)


def test_switch_sequence_columns_are_bigint() -> None:
    from sqlalchemy import BigInteger

    from zasky.storage.models import ProcessedSwitchEvent, SwitchConnectionState

    assert isinstance(
        SwitchConnectionState.__table__.c.highest_processed_sequence.type,
        BigInteger,
    )
    assert isinstance(
        ProcessedSwitchEvent.__table__.c.event_sequence.type,
        BigInteger,
    )
