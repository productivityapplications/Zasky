from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime

import pytest

from tests.unit.test_scheduler import seed_plan
from zasky.access.approvals import ApprovalCommand
from zasky.app import ZaskyApp
from zasky.config import Settings
from zasky.switch.events import MessageEvent


class FakeExecution:
    async def run(self, *, task, instruction=None):
        return {
            "output": (
                "## 1. The Deliverable\n\nSynthetic draft.\n\n"
                "## 2. What I Did\n\nDrafted from the task title.\n\n"
                "## 3. Verification Checklist\n\n- [ ] Review the draft."
            ),
            "model": "fake-model",
            "prompt_tokens": 10,
            "completion_tokens": 10,
        }


class FakeDiscord:
    def __init__(self) -> None:
        self.results: list[dict] = []
        self.delivered = True

    async def send_execution_result(self, **kwargs) -> bool:
        self.results.append(kwargs)
        return self.delivered

    async def close(self) -> None:
        return None


def event(body: str = "delegate test") -> MessageEvent:
    return MessageEvent.model_validate(
        {
            "event": "message",
            "id": 1,
            "data": {
                "type": "message",
                "room_id": "room-1",
                "payload": {
                    "addressed": True,
                    "sender": "@owner:test",
                    "sender_name": "owner",
                    "message_id": "message-1",
                    "body": body,
                },
                "sequence": 1,
            },
        }
    )


async def make_app(tmp_path, settings: Settings):
    configured = settings.model_copy(
        update={
            "database_url": f"sqlite+aiosqlite:///{tmp_path / 'delegation-app.db'}"
        }
    )
    app = ZaskyApp(configured)
    await app.db.init()
    await seed_plan(
        app.db, start_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    )
    app.execution = FakeExecution()  # type: ignore[assignment]
    app.discord = FakeDiscord()  # type: ignore[assignment]
    return app


@pytest.mark.asyncio
async def test_app_offers_delegation_for_explicit_inability(
    tmp_path, settings: Settings
) -> None:
    app = await make_app(tmp_path, settings)
    try:
        reply = await app._maybe_offer_delegation(
            "I can't do the demo narration today"
        )
        assert reply is not None
        assert "You don't have time for" in reply
        assert "`delegate ZK-" in reply
    finally:
        await app.db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_delegate_command_runs_subagent_and_signoff_completes_task(
    tmp_path, settings: Settings
) -> None:
    app = await make_app(tmp_path, settings)
    try:
        offer = await app._maybe_offer_delegation(
            "I can't do the demo narration today"
        )
        assert offer is not None
        code = re.search(r"delegate (ZK-[A-Z0-9]{4})", offer)
        assert code is not None

        reply, outcome = await app._handle_delegate_command(
            ApprovalCommand(action="delegate", code=code.group(1)),
            event(),
        )
        assert outcome == "approval_applied"
        assert "Execution ready" in reply
        execution = re.search(r"approve execution (ZK-[A-Z0-9]{4})", reply)
        assert execution is not None
        fake_discord = app.discord
        assert isinstance(fake_discord, FakeDiscord)
        assert fake_discord.results
        body = str(fake_discord.results[0]["body"])
        assert "## 1. The Deliverable" in body
        assert "approve execution ZK-" in body

        approved, approved_outcome = await app._handle_execution_approval(
            ApprovalCommand(
                action="approve_execution", code=execution.group(1)
            ),
            event(),
        )
        assert approved_outcome == "approval_applied"
        assert "marked complete" in approved
        detail = await app.domain.task_detail("task-1")
        assert detail["status"] == "completed"
    finally:
        await app.db.close(close_connections=False)
        await asyncio.sleep(0.2)
