from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from tests.unit.test_scheduler import seed_plan
from zasky.config import Settings
from zasky.domain.delegation import DelegationService
from zasky.domain.errors import DomainError
from zasky.domain.schemas import CompleteTaskRequest
from zasky.domain.service import DomainService
from zasky.storage.database import Database


@pytest.mark.asyncio
async def test_delegation_proposal_start_signoff_and_completion(
    tmp_path, settings: Settings
) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'delegation.db'}")
    await db.init()
    domain = DomainService(db, settings)
    delegations = DelegationService(db, settings)
    try:
        await seed_plan(
            db, start_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
        )
        assert delegations.looks_like_trigger(
            "I can't do the demo narration today"
        )
        task = await delegations.find_task_from_text(
            "I can't do the demo narration today"
        )
        assert task is not None
        assert task["id"] == "task-1"

        proposal = await delegations.propose(task["id"])
        assert proposal["code"].startswith("ZK-")
        assert proposal["status"] == "pending"

        started = await delegations.start(
            proposal["code"], actor_id="@owner:test"
        )
        assert started["execution_code"].startswith("ZK-")
        assert started["already"] is None

        output = (
            "## 1. The Deliverable\n\nDraft.\n\n"
            "## 2. What I Did\n\nDrafted.\n\n"
            "## 3. Verification Checklist\n\n- [ ] Review."
        )
        await delegations.mark_awaiting_signoff(
            str(started["execution_code"]), output
        )
        stored = await delegations.get_by_execution_code(
            str(started["execution_code"])
        )
        assert stored is not None
        assert stored.status == "awaiting_signoff"
        assert stored.output_markdown == output

        approved = await delegations.approve_execution(
            str(started["execution_code"]),
            actor_id="@owner:test",
            domain=domain,
        )
        assert approved["status"] == "completed"
        detail = await domain.task_detail("task-1")
        assert detail["status"] == "completed"

        again = await delegations.approve_execution(
            str(started["execution_code"]),
            actor_id="@owner:test",
            domain=domain,
        )
        assert again["already"] == "completed"
    finally:
        await db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_delegation_trigger_requires_an_unambiguous_task(
    tmp_path, settings: Settings
) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'delegation-miss.db'}")
    await db.init()
    delegations = DelegationService(db, settings)
    try:
        await seed_plan(
            db, start_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
        )
        assert await delegations.find_task_from_text("I can't do it") is None
    finally:
        await db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_delegation_proposal_rejects_completed_task(
    tmp_path, settings: Settings
) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'delegation-complete.db'}")
    await db.init()
    domain = DomainService(db, settings)
    delegations = DelegationService(db, settings)
    try:
        await seed_plan(
            db, start_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
        )
        await domain.complete_task(CompleteTaskRequest(task_id="task-1"))
        with pytest.raises(DomainError) as excinfo:
            await delegations.propose("task-1")
        assert excinfo.value.code == "CONFLICT"
    finally:
        await db.close(close_connections=False)
        await asyncio.sleep(0.2)
