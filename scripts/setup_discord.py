#!/usr/bin/env python3
"""One-off Discord server setup for Zasky HQ.

Creates the Zasky HQ category and its five text channels through the Discord
REST API. This script is intentionally independent of Switch.

The script is idempotent:
- an existing category with the same name is reused;
- an existing channel with the same name inside that category is reused;
- an existing channel with the same name outside the category is treated as a
  conflict and the script stops rather than moving someone else's channel.

It never prints the bot token. It writes a local JSON map and prints the exact
DISCORD_* environment lines needed by the Zasky backend.

Required bot permissions:
- View Channels
- Manage Channels

Example (do not run until reviewed):

    python scripts/setup_discord.py \
      --env-file /root/Zasky-secrets/zasky.env \
      --guild-id YOUR_DISCORD_SERVER_ID

The bot token can come from any of these environment names:
DISCORD_BOT_TOKEN, DISCORD_APP_BOT_TOKEN, DISCORD_TOKEN, BOT_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "discord_channels.json"
DEFAULT_API_BASE = "https://discord.com/api/v10"
CATEGORY_NAME = "Zasky HQ"

CHANNELS: tuple[tuple[str, str], ...] = (
    ("zasky-control", "Zasky control, commands and approval surface."),
    ("daily-briefings", "Approved Daily Briefings from Zasky."),
    ("reconcile-alerts", "Approved recovery and reconciliation summaries."),
    ("ai-workspace", "Execution Sub-Agent results and working notes."),
    ("dashboard-sync", "Dashboard sync and planning status notices."),
)

ENV_NAMES = {
    "zasky-control": "DISCORD_CONTROL_CHANNEL_ID",
    "daily-briefings": "DISCORD_DAILY_BRIEFINGS_CHANNEL_ID",
    "reconcile-alerts": "DISCORD_RECONCILE_ALERTS_CHANNEL_ID",
    "ai-workspace": "DISCORD_AI_WORKSPACE_CHANNEL_ID",
    "dashboard-sync": "DISCORD_DASHBOARD_SYNC_CHANNEL_ID",
}


class SetupError(RuntimeError):
    """A setup failure that is safe to print."""


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines without overwriting process environment values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def snowflake(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned.isdigit() or len(cleaned) < 15:
        raise SetupError(f"{label} must be a Discord snowflake ID (digits only).")
    return cleaned


class DiscordClient:
    """Small REST client with bounded rate-limit and server-error retries."""

    def __init__(self, token: str, *, api_base: str, timeout: float) -> None:
        self._client = httpx.Client(
            base_url=api_base.rstrip("/"),
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": "ZaskySetup/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        for attempt in range(5):
            try:
                response = self._client.request(method, path, json=json_body)
            except httpx.HTTPError as exc:
                raise SetupError(
                    f"Discord request failed: {type(exc).__name__}"
                ) from exc

            if response.status_code == 429:
                retry_after = 1.0
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        retry_after = float(payload.get("retry_after", 1.0))
                except (TypeError, ValueError):
                    pass
                time.sleep(min(max(retry_after, 0.25), 10.0))
                continue

            if response.status_code >= 500:
                if attempt < 4:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise SetupError(
                    f"Discord API {method} {path} returned HTTP "
                    f"{response.status_code}."
                )

            if response.status_code >= 400:
                message = ""
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        message = str(payload.get("message", ""))[:200]
                except (TypeError, ValueError):
                    pass
                suffix = f": {message}" if message else ""
                raise SetupError(
                    f"Discord API {method} {path} returned HTTP "
                    f"{response.status_code}{suffix}"
                )

            if response.status_code == 204:
                return {}
            try:
                return response.json()
            except ValueError as exc:
                raise SetupError(
                    f"Discord API {method} {path} returned non-JSON."
                ) from exc

        raise SetupError("Discord API rate-limit retries exhausted.")

    def bot_identity(self) -> dict[str, Any]:
        payload = self.request("GET", "/users/@me")
        if not isinstance(payload, dict):
            raise SetupError("Discord bot identity response was invalid.")
        return payload

    def guild(self, guild_id: str) -> dict[str, Any]:
        payload = self.request("GET", f"/guilds/{guild_id}")
        if not isinstance(payload, dict):
            raise SetupError("Discord guild response was invalid.")
        return payload

    def channels(self, guild_id: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"/guilds/{guild_id}/channels")
        if not isinstance(payload, list):
            raise SetupError("Discord channel list response was invalid.")
        return [item for item in payload if isinstance(item, dict)]

    def create_category(self, guild_id: str, name: str) -> dict[str, Any]:
        payload = self.request(
            "POST",
            f"/guilds/{guild_id}/channels",
            json_body={"name": name, "type": 4},
        )
        if not isinstance(payload, dict):
            raise SetupError("Discord category creation response was invalid.")
        return payload

    def create_text_channel(
        self,
        guild_id: str,
        *,
        name: str,
        topic: str,
        category_id: str,
        position: int,
    ) -> dict[str, Any]:
        payload = self.request(
            "POST",
            f"/guilds/{guild_id}/channels",
            json_body={
                "name": name,
                "type": 0,
                "parent_id": category_id,
                "topic": topic,
                "position": position,
            },
        )
        if not isinstance(payload, dict):
            raise SetupError("Discord channel creation response was invalid.")
        return payload


def ensure_category(
    client: DiscordClient,
    *,
    guild_id: str,
    channels: list[dict[str, Any]],
    name: str,
    dry_run: bool,
) -> tuple[dict[str, Any], bool]:
    matches = [
        item
        for item in channels
        if item.get("type") == 4 and item.get("name") == name
    ]
    if len(matches) > 1:
        print(
            f"WARNING: {len(matches)} categories named {name!r} exist; "
            "using the first one.",
            file=sys.stderr,
        )
    if matches:
        return matches[0], False
    if dry_run:
        return {"id": f"DRY_RUN_{name.replace(' ', '_')}", "name": name}, True
    return client.create_category(guild_id, name), True


def ensure_text_channel(
    client: DiscordClient,
    *,
    guild_id: str,
    channels: list[dict[str, Any]],
    category_id: str,
    category_name: str,
    name: str,
    topic: str,
    position: int,
    dry_run: bool,
) -> tuple[dict[str, Any], bool]:
    matches = [
        item
        for item in channels
        if item.get("type") == 0 and item.get("name") == name
    ]
    if len(matches) > 1:
        print(
            f"WARNING: {len(matches)} text channels named #{name} exist; "
            "using the first one.",
            file=sys.stderr,
        )
    if matches:
        existing = matches[0]
        if existing.get("parent_id") != category_id:
            raise SetupError(
                f"#{name} already exists outside the {category_name} category. "
                "Refusing to move it automatically."
            )
        return existing, False
    if dry_run:
        return {
            "id": f"DRY_RUN_{name.replace('-', '_')}",
            "name": name,
            "parent_id": category_id,
        }, True
    return (
        client.create_text_channel(
            guild_id,
            name=name,
            topic=topic,
            category_id=category_id,
            position=position,
        ),
        True,
    )


def write_mapping(path: Path, mapping: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the Zasky HQ Discord category and channels."
    )
    parser.add_argument(
        "--env-file",
        default=os.environ.get(
            "DISCORD_SETUP_ENV_FILE", "/root/Zasky-secrets/zasky.env"
        ),
        help="Optional protected env file containing the bot token and guild ID.",
    )
    parser.add_argument(
        "--guild-id",
        default="",
        help="Discord server/guild ID. Defaults to DISCORD_GUILD_ID.",
    )
    parser.add_argument(
        "--category-name",
        default=CATEGORY_NAME,
        help=f"Category name (default: {CATEGORY_NAME}).",
    )
    parser.add_argument(
        "--api-base-url",
        default="",
        help=f"Discord REST base URL (default: {DEFAULT_API_BASE}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON mapping output (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="Do not write the JSON mapping.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and print planned actions without creating anything.",
    )
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    token = first_env(
        (
            "DISCORD_BOT_TOKEN",
            "DISCORD_APP_BOT_TOKEN",
            "DISCORD_TOKEN",
            "BOT_TOKEN",
        )
    )
    if not token:
        raise SetupError(
            "No Discord bot token found. Set DISCORD_BOT_TOKEN in the "
            "protected environment."
        )
    guild_value = (
        args.guild_id
        or os.environ.get("DISCORD_GUILD_ID", "")
        or os.environ.get("DISCORD_SERVER_ID", "")
    )
    guild_id = snowflake(guild_value, "Guild ID")
    category_name = args.category_name.strip()
    if not category_name:
        raise SetupError("Category name must not be empty.")

    api_base = (
        args.api_base_url
        or os.environ.get("DISCORD_API_BASE_URL", "")
        or DEFAULT_API_BASE
    )
    client = DiscordClient(
        token,
        api_base=api_base,
        timeout=args.timeout,
    )
    try:
        bot = client.bot_identity()
        bot_name = str(bot.get("username") or "unknown")
        guild = client.guild(guild_id)
        guild_name = str(guild.get("name") or guild_id)
        print(f"Bot: {bot_name}")
        print(f"Guild: {guild_name} ({guild_id})")

        channels = client.channels(guild_id)
        category, category_created = ensure_category(
            client,
            guild_id=guild_id,
            channels=channels,
            name=category_name,
            dry_run=args.dry_run,
        )
        category_id = str(category.get("id") or "")
        if not category_id:
            raise SetupError("Discord did not return a category ID.")
        action = "created" if category_created else "reused"
        print(f"Category {action}: {category_name} ({category_id})")

        channel_map: dict[str, str] = {}
        for position, (name, topic) in enumerate(CHANNELS):
            channel, created = ensure_text_channel(
                client,
                guild_id=guild_id,
                channels=channels,
                category_id=category_id,
                category_name=category_name,
                name=name,
                topic=topic,
                position=position,
                dry_run=args.dry_run,
            )
            channel_id = str(channel.get("id") or "")
            if not channel_id:
                raise SetupError(f"Discord did not return an ID for #{name}.")
            action = "created" if created else "reused"
            print(f"Channel {action}: #{name} ({channel_id})")
            channel_map[name] = channel_id

        mapping = {
            "guild_id": guild_id,
            "category": {"id": category_id, "name": category_name},
            "channels": channel_map,
        }
        if not args.no_output and not args.dry_run:
            write_mapping(args.output, mapping)
            print(f"Mapping written to {args.output}")

        print("")
        print("Add these lines to the protected Zasky env file:")
        print(f"DISCORD_GUILD_ID={guild_id}")
        for name, _topic in CHANNELS:
            print(f"{ENV_NAMES[name]}={channel_map[name]}")
        print("")
        print(
            "Keep DISCORD_BOT_TOKEN in the same protected env file; "
            "the script never prints it."
        )
        if args.dry_run:
            print("Dry run complete. Nothing was created.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
