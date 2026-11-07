from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from zasky.config import Settings
from zasky.integrations.discord import DiscordNotificationError, DiscordNotifier

DAILY_ID = "111111111111111111"
RECONCILE_ID = "222222222222222222"
AI_ID = "333333333333333333"


def configured(settings: Settings, **updates: Any) -> Settings:
    values: dict[str, Any] = {
        "discord_bot_token": SecretStr("synthetic-bot-token"),
        "discord_daily_briefings_channel_id": DAILY_ID,
        "discord_reconcile_alerts_channel_id": RECONCILE_ID,
        "discord_ai_workspace_channel_id": AI_ID,
    }
    values.update(updates)
    return settings.model_copy(update=values)


def mock_client(
    handler: Any,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://discord.test/api/v10",
    )


@pytest.mark.asyncio
async def test_daily_briefing_uses_configured_channel(settings: Settings) -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v10/channels/{DAILY_ID}/messages"
        assert request.headers["authorization"] == "Bot synthetic-bot-token"
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "message-1"})

    client = mock_client(handler)
    notifier = DiscordNotifier(configured(settings), client=client)
    try:
        delivered = await notifier.send_daily_briefing(
            "📅 **Daily Briefing — Friday**\n\n**MUST DO:** Synthetic task",
            "2026-11-06",
        )
        assert delivered is True
        assert captured[0]["allowed_mentions"] == {"parse": []}
        assert "Daily Briefing" in captured[0]["content"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_reconcile_summary_lists_kept_items(settings: Settings) -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v10/channels/{RECONCILE_ID}/messages"
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "message-2"})

    client = mock_client(handler)
    notifier = DiscordNotifier(configured(settings), client=client)
    try:
        delivered = await notifier.send_reconcile_summary(
            code="ZK-ABCD",
            local_date="2026-11-06",
            items=[
                {
                    "title": "Check backup restore evidence",
                    "disposition": "must",
                    "est_min": 30,
                },
                {
                    "title": "Write the demo script",
                    "disposition": "should",
                    "est_min": 45,
                },
            ],
            moves=2,
            feasibility="week_holds",
        )
        assert delivered is True
        content = captured[0]["content"]
        assert "ZK-ABCD" in content
        assert "Check backup restore evidence" in content
        assert "Moved within the week:** 2" in content
        assert "week\\_holds" in content
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_execution_result_uses_ai_workspace(settings: Settings) -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v10/channels/{AI_ID}/messages"
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "message-3"})

    client = mock_client(handler)
    notifier = DiscordNotifier(configured(settings), client=client)
    try:
        delivered = await notifier.send_execution_result(
            title="Draft complete",
            body="The execution sub-agent produced a first draft.",
            task_id="task-1",
        )
        assert delivered is True
        content = captured[0]["content"]
        assert "Execution Sub-Agent result" in content
        assert "first draft" in content
        assert "task-1" in content
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unconfigured_channel_is_a_noop(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unconfigured notifier must not call Discord")

    client = mock_client(handler)
    notifier = DiscordNotifier(
        configured(settings, discord_daily_briefings_channel_id=None),
        client=client,
    )
    try:
        assert await notifier.send_daily_briefing("test", "2026-11-06") is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_permission_failure_is_reported_without_body(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "Missing Permissions", "code": 50013},
        )

    client = mock_client(handler)
    notifier = DiscordNotifier(configured(settings), client=client)
    try:
        with pytest.raises(DiscordNotificationError) as excinfo:
            await notifier.send_execution_result(title="x", body="y")
        assert excinfo.value.code == "DISCORD_HTTP_403"
        assert "synthetic-bot-token" not in str(excinfo.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_429_is_retried(settings: Settings) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"retry_after": 0})
        return httpx.Response(200, json={"id": "message-4"})

    client = mock_client(handler)
    notifier = DiscordNotifier(configured(settings), client=client)
    try:
        assert await notifier.send_daily_briefing("test", "2026-11-06") is True
        assert calls == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_content_is_truncated_to_discord_limit(settings: Settings) -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "message-5"})

    client = mock_client(handler)
    notifier = DiscordNotifier(configured(settings), client=client)
    try:
        await notifier.send_execution_result(title="Long", body="x" * 5000)
        content = captured[0]["content"]
        assert len(content) <= 2000
        assert content.endswith("…")
    finally:
        await client.aclose()
