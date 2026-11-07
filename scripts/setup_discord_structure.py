#!/usr/bin/env python3
"""Create/reorder the final Zasky hackathon Discord structure.

Idempotent: existing categories/channels are reused and moved, not duplicated.
The bot token is read from the protected env file and never printed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = "/root/Zasky-secrets/zasky.env"
API_BASE = "https://discord.com/api/v10"

EVERYONE_ALLOW = 1 << 10  # VIEW_CHANNEL
EVERYONE_DENY = (
    (1 << 11)  # SEND_MESSAGES
    | (1 << 6)  # ADD_REACTIONS
    | (1 << 34)  # CREATE_PUBLIC_THREADS
    | (1 << 36)  # CREATE_PRIVATE_THREADS
    | (1 << 38)  # SEND_MESSAGES_IN_THREADS
)

CATEGORIES = [
    ("START HERE", 0, True),
    ("ZASKY CONTROL", 1, False),
    ("AGENT OUTPUTS", 2, True),
    ("COMMUNITY", 3, False),
]

CHANNELS = [
    (
        "welcome-and-how-to-test",
        "START HERE",
        0,
        "Welcome to Zasky. Start here: how to test the dashboard, Discord, and judge sandbox.",
    ),
    (
        "zasky-control",
        "ZASKY CONTROL",
        0,
        "Talk to Zasky, approve planning proposals, and run the owner workflow.",
    ),
    (
        "judges-sandbox",
        "ZASKY CONTROL",
        1,
        "Test Zasky live! Type @zasky What is my plan? to see the multi-agent system in action.",
    ),
    (
        "daily-briefings",
        "AGENT OUTPUTS",
        0,
        "Approved Daily Briefings from Zasky.",
    ),
    (
        "reconcile-alerts",
        "AGENT OUTPUTS",
        1,
        "Approved recovery and reconciliation summaries.",
    ),
    (
        "ai-workspace",
        "AGENT OUTPUTS",
        2,
        "Structured Execution Agent deliverables and verification checklists.",
    ),
    (
        "dashboard-sync",
        "AGENT OUTPUTS",
        3,
        "Dashboard sync and planning status notices.",
    ),
    (
        "general-chat",
        "COMMUNITY",
        0,
        "Community chat for the Zasky hackathon demo.",
    ),
]


class DiscordError(RuntimeError):
    pass


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


class Discord:
    def __init__(self, token: str) -> None:
        self.client = httpx.Client(
            base_url=API_BASE,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": "ZaskySetup/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self.client.close()

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        for attempt in range(8):
            try:
                response = self.client.request(method, path, json=body)
            except httpx.HTTPError as exc:
                raise DiscordError(
                    f"{method} {path} failed: {type(exc).__name__}"
                ) from exc
            if response.status_code == 429:
                retry = 1.0
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        retry = float(payload.get("retry_after", 1.0))
                except (TypeError, ValueError):
                    pass
                time.sleep(min(max(retry, 0.5), 60.0))
                continue
            if response.status_code >= 500 and attempt < 4:
                time.sleep(min(2**attempt, 8))
                continue
            if response.status_code >= 400:
                message = ""
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        message = str(payload.get("message", ""))[:200]
                except (TypeError, ValueError):
                    pass
                raise DiscordError(
                    f"{method} {path} -> HTTP {response.status_code}"
                    + (f": {message}" if message else "")
                )
            if response.status_code == 204:
                return {}
            try:
                return response.json()
            except ValueError as exc:
                raise DiscordError(f"{method} {path} returned non-JSON") from exc
        raise DiscordError("Discord rate-limit retries exhausted")

    def channels(self, guild_id: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"/guilds/{guild_id}/channels")
        if not isinstance(payload, list):
            raise DiscordError("channel list was invalid")
        return [item for item in payload if isinstance(item, dict)]


def set_readonly_overwrite(
    overwrites: list[dict[str, Any]], guild_id: str
) -> list[dict[str, Any]]:
    result = [
        item
        for item in overwrites
        if not (str(item.get("type")) == "0" and str(item.get("id")) == guild_id)
    ]
    result.append(
        {
            "id": guild_id,
            "type": 0,
            "allow": str(EVERYONE_ALLOW),
            "deny": str(EVERYONE_DENY),
        }
    )
    return result


def find_category(
    channels: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in channels
            if item.get("type") == 4 and item.get("name") == name
        ),
        None,
    )


def find_channel(
    channels: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in channels
            if item.get("type") == 0 and item.get("name") == name
        ),
        None,
    )


def ensure_category(
    client: Discord,
    *,
    guild_id: str,
    channels: list[dict[str, Any]],
    name: str,
    position: int,
    read_only: bool,
) -> tuple[dict[str, Any], bool]:
    existing = find_category(channels, name)
    if read_only:
        print(
            f"NOTE: {name} should be read-only; category permission overwrites "
            "are applied separately because the bot cannot edit @everyone.",
            file=sys.stderr,
        )
    if existing is None:
        payload = client.request(
            "POST",
            f"/guilds/{guild_id}/channels",
            {"name": name, "type": 4, "position": position},
        )
        if not isinstance(payload, dict):
            raise DiscordError(f"category {name} response was invalid")
        return payload, True
    if int(existing.get("position") or 0) == position:
        return existing, False
    payload = client.request(
        "PATCH",
        f"/channels/{existing['id']}",
        {"position": position},
    )
    if not isinstance(payload, dict):
        raise DiscordError(f"category {name} update response was invalid")
    return payload, False


def ensure_text_channel(
    client: Discord,
    *,
    guild_id: str,
    channels: list[dict[str, Any]],
    name: str,
    topic: str,
    parent_id: str,
    position: int,
) -> tuple[dict[str, Any], bool]:
    existing = find_channel(channels, name)
    if existing is None:
        payload = client.request(
            "POST",
            f"/guilds/{guild_id}/channels",
            {
                "name": name,
                "type": 0,
                "topic": topic,
                "parent_id": parent_id,
                "position": position,
            },
        )
        if not isinstance(payload, dict):
            raise DiscordError(f"channel {name} response was invalid")
        return payload, True
    fields: dict[str, Any] = {}
    if existing.get("parent_id") != parent_id:
        fields["parent_id"] = parent_id
    if (existing.get("topic") or "") != topic:
        fields["topic"] = topic
    if int(existing.get("position") or 0) != position:
        fields["position"] = position
    if not fields:
        return existing, False
    payload = client.request(
        "PATCH",
        f"/channels/{existing['id']}",
        fields,
    )
    if not isinstance(payload, dict):
        raise DiscordError(f"channel {name} update response was invalid")
    return payload, False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=DEFAULT_ENV)
    args = parser.parse_args()
    load_env(Path(args.env_file))
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
    if not token:
        raise DiscordError("DISCORD_BOT_TOKEN is missing from the env file")
    if not guild_id.isdigit():
        raise DiscordError("DISCORD_GUILD_ID is missing or invalid")

    client = Discord(token)
    try:
        channels = client.channels(guild_id)
        print(f"Existing channels: {len(channels)}")
        categories: dict[str, str] = {}
        for name, position, read_only in CATEGORIES:
            category, created = ensure_category(
                client,
                guild_id=guild_id,
                channels=channels,
                name=name,
                position=position,
                read_only=read_only,
            )
            category_id = str(category.get("id") or "")
            if not category_id:
                raise DiscordError(f"category {name} has no ID")
            categories[name] = category_id
            print(f"{'Created' if created else 'Updated'} category: {name}")
            channels = client.channels(guild_id)

        for name, category_name, position, topic in CHANNELS:
            channel, created = ensure_text_channel(
                client,
                guild_id=guild_id,
                channels=channels,
                name=name,
                topic=topic,
                parent_id=categories[category_name],
                position=position,
            )
            channel_id = str(channel.get("id") or "")
            if not channel_id:
                raise DiscordError(f"channel {name} has no ID")
            print(
                f"{'Created' if created else 'Updated'} channel: "
                f"#{name} -> {category_name}"
            )
            channels = client.channels(guild_id)

        # Remove empty legacy categories created by earlier setup runs.
        channels = client.channels(guild_id)
        for legacy_name in ("Zasky Test Category", "Zasky HQ"):
            legacy = find_category(channels, legacy_name)
            if legacy is None:
                continue
            children = [
                item for item in channels if item.get("parent_id") == legacy["id"]
            ]
            if not children:
                client.request("DELETE", f"/channels/{legacy['id']}")
                print(f"Deleted empty legacy category: {legacy_name}")
                channels = client.channels(guild_id)

        print("")
        print("Final structure:")
        for category_name, _position, _read_only in CATEGORIES:
            print(f"  {category_name}")
            for name, target_category, _pos, _topic in CHANNELS:
                if target_category == category_name:
                    print(f"    #{name}")
        print("")
        print("Judges sandbox topic set.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiscordError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
