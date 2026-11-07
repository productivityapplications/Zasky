"""Narrow outbound Discord notifier for Zasky's owner channels.

The chat interface remains Switch. This module only posts application-generated
briefings, recovery summaries and execution results to configured channel IDs.
It never reads inbound Discord events and is never exposed as a model tool.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from zasky.config import Settings

logger = logging.getLogger(__name__)

_DISCORD_MESSAGE_LIMIT = 2000
_MAX_RETRIES = 3


class DiscordNotificationError(RuntimeError):
    """A delivery failed without exposing message content or the bot token."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _secret_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value()).strip()
    return str(value).strip()


def _truncate(text: str, limit: int = _DISCORD_MESSAGE_LIMIT) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _display_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%A, %b %-d")


def _escape_md(text: str) -> str:
    escaped = str(text).replace("\\", "\\\\")
    for char in ("*", "_", "`", "~", "|"):
        escaped = escaped.replace(char, "\\" + char)
    return escaped


class DiscordNotifier:
    """Process-lifetime Discord REST client for configured notification channels."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._token = _secret_value(settings.discord_bot_token)
        self._owns_client = client is None
        if client is not None:
            self._client: httpx.AsyncClient | None = client
        elif self._token:
            self._client = httpx.AsyncClient(
                base_url=settings.discord_api_base_url,
                timeout=httpx.Timeout(20.0, connect=10.0),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=60.0,
                ),
                headers={
                    "Authorization": f"Bot {self._token}",
                    "User-Agent": "Zasky/0.1",
                    "Accept": "application/json",
                },
            )
        else:
            self._client = None

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _channel(self, name: str) -> str | None:
        return {
            "daily": self._settings.discord_daily_briefings_channel_id,
            "reconcile": self._settings.discord_reconcile_alerts_channel_id,
            "ai_workspace": self._settings.discord_ai_workspace_channel_id,
        }.get(name)

    async def _send_message(self, channel_id: str, content: str) -> bool:
        if self._client is None or not self._token:
            return False
        payload = {
            "content": _truncate(content),
            "allowed_mentions": {"parse": []},
        }
        last_code = "DISCORD_DELIVERY_FAILED"
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.post(
                    f"/channels/{channel_id}/messages",
                    json=payload,
                    headers={"Authorization": f"Bot {self._token}"},
                )
            except httpx.HTTPError as exc:
                last_code = f"DISCORD_UNREACHABLE_{type(exc).__name__}"
                if attempt + 1 < _MAX_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise DiscordNotificationError(last_code) from exc

            if response.status_code == 429:
                last_code = "DISCORD_RATE_LIMITED"
                retry_after = 1.0
                try:
                    body = response.json()
                    if isinstance(body, dict):
                        retry_after = float(body.get("retry_after", 1.0))
                except (ValueError, TypeError):
                    pass
                await asyncio.sleep(min(max(retry_after, 0.25), 10.0))
                continue
            if response.status_code >= 500:
                last_code = f"DISCORD_HTTP_{response.status_code}"
                if attempt + 1 < _MAX_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise DiscordNotificationError(last_code)
            if response.status_code >= 400:
                raise DiscordNotificationError(
                    f"DISCORD_HTTP_{response.status_code}"
                )
            return True
        raise DiscordNotificationError(last_code)

    async def send_daily_briefing(self, briefing: str, local_date: str) -> bool:
        channel_id = self._channel("daily")
        if channel_id is None or self._client is None:
            return False
        return await self._send_message(channel_id, briefing)

    async def send_reconcile_summary(
        self,
        *,
        code: str,
        local_date: str,
        items: list[dict[str, Any]],
        moves: int,
        feasibility: str | None,
    ) -> bool:
        channel_id = self._channel("reconcile")
        if channel_id is None or self._client is None:
            return False
        lines = [
            f"♻️ **Recovery plan approved** `{_escape_md(code)}`",
            "",
            f"**Date:** {_display_date(local_date)}",
            "**Kept today:**",
        ]
        if items:
            for item in items:
                marker = "📌" if item.get("disposition") == "must" else "✅"
                title = _escape_md(str(item.get("title") or "Untitled task"))
                minutes = item.get("est_min")
                suffix = f" — {minutes} min" if isinstance(minutes, int) else ""
                lines.append(f"- {marker} **{title}**{suffix}")
        else:
            lines.append("- No tasks kept today.")
        if moves:
            lines.extend(["", f"**Moved within the week:** {moves}"])
        if feasibility:
            lines.extend(["", f"**Week status:** {_escape_md(feasibility)}"])
        lines.extend(
            [
                "",
                "*Approved by the owner. Planning state is stored in Postgres.*",
            ]
        )
        return await self._send_message(channel_id, "\n".join(lines))

    async def send_execution_result(
        self,
        *,
        title: str,
        body: str,
        task_id: str | None = None,
    ) -> bool:
        channel_id = self._channel("ai_workspace")
        if channel_id is None or self._client is None:
            return False
        content = (
            f"🧪 **Execution Sub-Agent result — {_escape_md(title)}**\n\n"
            f"{body.strip()}"
        )
        if task_id:
            content += f"\n\n**Task:** `{_escape_md(task_id)}`"
        return await self._send_message(channel_id, content)
