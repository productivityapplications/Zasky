#!/usr/bin/env python3
"""Post or refresh the pinned Zasky server guide in the welcome channel.

The script uses only the Discord REST API. It discovers the welcome channel by
name, updates an existing guide when one is already present, and otherwise
creates a new guide. Secrets are read from the protected env file and are never
printed.

Usage:
    uv run python scripts/post_welcome_guide.py \
        --env-file /root/Zasky-secrets/zasky.env
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = "https://discord.com/api/v10"
DASHBOARD_URL = "https://zasky-flax.vercel.app/"
DEMO_URL = "https://github.com/productivityapplications/Zasky/blob/main/artifacts/demo/zasky-demo.mp4"
WELCOME_CHANNEL_NAME = "welcome-and-how-to-test"
GUIDE_MARKER = "Zasky Server Guide"
GUIDE_VERSION = "v1"


def load_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "ZaskyServerGuide/1.0",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        API + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 204:
                return None
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Discord API {method} {path} -> {exc.code}: {detail}") from exc


def find_channel(
    guild_id: str, token: str, configured_id: str | None
) -> dict[str, Any]:
    channels = request("GET", f"/guilds/{guild_id}/channels", token)
    if configured_id:
        for channel in channels:
            if str(channel.get("id")) == str(configured_id):
                return channel
    for channel in channels:
        if (
            channel.get("type") == 0
            and channel.get("name") == WELCOME_CHANNEL_NAME
        ):
            return channel
    raise RuntimeError(
        f"Could not find #{WELCOME_CHANNEL_NAME} in guild {guild_id}"
    )


def guide_payload(guild_id: str, sandbox_channel_id: str | None) -> dict[str, Any]:
    fields: list[dict[str, Any]] = [
        {
            "name": "🧭  #zasky-control",
            "value": (
                "Talk to Zasky here for main planning, proposals, approvals "
                "and the owner workflow."
            ),
            "inline": False,
        },
        {
            "name": "🧪  #judges-sandbox",
            "value": (
                "A safe, isolated SQLite sandbox for judges. Test Zasky live "
                "without touching owner data. **No `@zasky` mention is required.**"
            ),
            "inline": False,
        },
        {
            "name": "📬  Read-only agent outputs",
            "value": (
                "**#daily-briefings** — approved daily briefings.\n"
                "**#reconcile-alerts** — recovery and reconciliation summaries.\n"
                "**#ai-workspace** — Execution Sub-Agent deliverables and "
                "verification checklists."
            ),
            "inline": False,
        },
        {
            "name": "⚡  Try it now in #judges-sandbox",
            "value": (
                "Try typing `@zasky what is my plan?` in the sandbox!\n"
                "```text\n"
                "hello\n"
                "@zasky what is my plan?\n"
                "@zasky reconcile my week\n"
                "```"
            ),
            "inline": False,
        },
        {
            "name": "🔗  Links",
            "value": (
                f"[Live dashboard]({DASHBOARD_URL}) · "
                f"[97-second demo]({DEMO_URL})"
            ),
            "inline": False,
        },
    ]

    components: list[dict[str, Any]] = []
    buttons: list[dict[str, Any]] = [
        {
            "type": 2,
            "style": 5,
            "label": "Open Dashboard",
            "url": DASHBOARD_URL,
        },
        {
            "type": 2,
            "style": 5,
            "label": "Watch Demo",
            "url": DEMO_URL,
        },
    ]
    if sandbox_channel_id:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": "Go to Sandbox",
                "url": (
                    f"https://discord.com/channels/{guild_id}/"
                    f"{sandbox_channel_id}"
                ),
            }
        )
    components.append({"type": 1, "components": buttons})

    return {
        "content": f"**{GUIDE_MARKER} {GUIDE_VERSION}**",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": "🚀 Welcome to Zasky — The Proactive Multi-Agent Task Manager",
                "description": (
                    "Zasky lives in Discord through Switch. It protects your "
                    "week, makes recovery cheap, and delegates safe digital "
                    "work to an Execution Sub-Agent.\n\n"
                    "**Start here → `#welcome-and-how-to-test` · test live → "
                    "`#judges-sandbox`**"
                ),
                "color": 0x7C3AED,
                "fields": fields,
                "footer": {
                    "text": "Zasky · Switch + Discord · The Cockpit"
                },
            }
        ],
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default="/root/Zasky-secrets/zasky.env",
        help="Protected env file containing DISCORD_BOT_TOKEN and DISCORD_GUILD_ID",
    )
    args = parser.parse_args()

    env = load_env(args.env_file)
    token = env.get("DISCORD_BOT_TOKEN", "")
    guild_id = env.get("DISCORD_GUILD_ID", "")
    configured_channel = env.get("DISCORD_WELCOME_CHANNEL_ID")
    sandbox_channel = env.get("SANDBOX_DISCORD_CHANNEL_ID")
    if not token or not guild_id:
        print(
            "DISCORD_BOT_TOKEN and DISCORD_GUILD_ID are required in the env file.",
            file=sys.stderr,
        )
        return 2

    channel = find_channel(guild_id, token, configured_channel)
    channel_id = str(channel["id"])
    payload = guide_payload(guild_id, sandbox_channel)

    recent = request(
        "GET", f"/channels/{channel_id}/messages?limit=50", token
    )
    existing = None
    for message in recent:
        if message.get("author", {}).get("bot") is not True:
            continue
        if message.get("content", "").startswith(f"**{GUIDE_MARKER}"):
            existing = message
            break
        for embed in message.get("embeds", []):
            if GUIDE_MARKER in str(embed.get("title", "")):
                existing = message
                break
        if existing is not None:
            break

    if existing is not None:
        message = request(
            "PATCH",
            f"/channels/{channel_id}/messages/{existing['id']}",
            token,
            payload,
        )
        action = "updated"
    else:
        message = request(
            "POST", f"/channels/{channel_id}/messages", token, payload
        )
        action = "created"

    message_id = str(message["id"])
    pin_status = "pinned"
    try:
        request(
            "PUT", f"/channels/{channel_id}/pins/{message_id}", token
        )
    except RuntimeError as exc:
        pin_status = f"pin skipped ({exc})"

    print(f"channel: #{channel.get('name')} ({channel_id})")
    print(f"message: {message_id} ({action})")
    print(f"pin: {pin_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
