#!/usr/bin/env python3
"""Post or refresh the "How it works" embed in each Zasky Discord channel.

The script is idempotent: it updates the existing guide in a channel instead of
creating duplicates. It attempts to pin each message; if the bot lacks Manage
Messages, the message is still posted and the pin failure is reported without
stopping the remaining channels.

Usage:
    uv run python scripts/post_pinned_guides.py \
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
GITHUB_URL = "https://github.com/productivityapplications/Zasky"
FOOTER = "Zasky HQ · The Cockpit · How it works v1"

CHANNELS = {
    "welcome-and-how-to-test": {
        "title": "🚀 Welcome to Zasky HQ",
        "description": (
            "Welcome to Zasky HQ! To test the bot live, go to "
            "`#judges-sandbox`. To see my real workflow, check out "
            "`#zasky-control` (messages are private). Use the links below for "
            "the dashboard and GitHub."
        ),
        "color": 0xF2EF69,
        "links": True,
    },
    "zasky-control": {
        "title": "📌 How it works — Owner control",
        "description": (
            "This is the Owner's private planning room. As a guest, you can "
            "see the channel exists, but message history is private for "
            "security. The bot responds here to the owner."
        ),
        "color": 0xFF6B5E,
    },
    "judges-sandbox": {
        "title": "📌 How it works — Judge sandbox",
        "description": (
            "Test Zasky live here! Try typing `@zasky hello` or "
            "`@zasky what is my plan? Battery medium.` to see the "
            "multi-agent system in action."
        ),
        "color": 0x9DEBB5,
    },
    "daily-briefings": {
        "title": "📌 How it works — Daily briefings",
        "description": (
            "When the Owner approves a daily plan, Zasky posts the formatted "
            "Daily Briefing here."
        ),
        "color": 0x8ED7F6,
    },
    "reconcile-alerts": {
        "title": "📌 How it works — Reconcile alerts",
        "description": (
            "When a day breaks, Zasky calculates the math to recover the week "
            "and posts the KEEP/MOVE/DROP alerts here."
        ),
        "color": 0xC7A3F3,
    },
    "ai-workspace": {
        "title": "📌 How it works — AI workspace",
        "description": (
            "When the Owner delegates a digital task, the Execution Sub-Agent "
            "does the work and posts the structured output here."
        ),
        "color": 0xFF8FAE,
    },
    "dashboard-sync": {
        "title": "📌 How it works — Dashboard sync",
        "description": (
            "Real-time sync events from the Vercel Web Dashboard appear here."
        ),
        "color": 0xF4D58D,
    },
}


def load_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
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
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "ZaskyPinnedGuides/1.0",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        return exc.code, detail


def guide_payload(spec: dict[str, Any]) -> dict[str, Any]:
    embed: dict[str, Any] = {
        "title": spec["title"],
        "description": spec["description"],
        "color": spec["color"],
        "footer": {"text": FOOTER},
    }
    fields: list[dict[str, Any]] = []
    if spec.get("links"):
        fields.append(
            {
                "name": "🔗 Links",
                "value": (
                    f"[Live dashboard]({DASHBOARD_URL}) · "
                    f"[GitHub repository]({GITHUB_URL})"
                ),
                "inline": False,
            }
        )
    if fields:
        embed["fields"] = fields

    payload: dict[str, Any] = {
        "content": "",
        "allowed_mentions": {"parse": []},
        "embeds": [embed],
    }
    if spec.get("links"):
        payload["components"] = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Open Dashboard",
                        "url": DASHBOARD_URL,
                    },
                    {
                        "type": 2,
                        "style": 5,
                        "label": "GitHub",
                        "url": GITHUB_URL,
                    },
                ],
            }
        ]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default="/root/Zasky-secrets/zasky.env",
        help="Protected env file with DISCORD_BOT_TOKEN and DISCORD_GUILD_ID",
    )
    args = parser.parse_args()
    env = load_env(args.env_file)
    token = env.get("DISCORD_BOT_TOKEN", "")
    guild_id = env.get("DISCORD_GUILD_ID", "")
    if not token or not guild_id:
        print(
            "DISCORD_BOT_TOKEN and DISCORD_GUILD_ID are required.",
            file=sys.stderr,
        )
        return 2

    status, me = request("GET", "/users/@me", token)
    if status != 200:
        print("Could not identify the bot account.", file=sys.stderr)
        return 2
    bot_id = str(me["id"])

    status, channels = request("GET", f"/guilds/{guild_id}/channels", token)
    if status != 200:
        print("Could not list guild channels.", file=sys.stderr)
        return 2
    by_name = {
        channel.get("name"): channel
        for channel in channels
        if channel.get("type") in {0, 5}
    }

    posted = 0
    pinned = 0
    pin_blocked: list[str] = []
    for name, spec in CHANNELS.items():
        channel = by_name.get(name)
        if channel is None:
            print(f"missing_channel #{name}")
            continue
        channel_id = str(channel["id"])
        payload = guide_payload(spec)
        status, recent = request(
            "GET", f"/channels/{channel_id}/messages?limit=50", token
        )
        existing: dict[str, Any] | None = None
        if status == 200 and isinstance(recent, list):
            for message in recent:
                if str(message.get("author", {}).get("id")) != bot_id:
                    continue
                content = str(message.get("content", ""))
                if "Zasky Server Guide" in content:
                    existing = message
                    break
                for embed in message.get("embeds", []):
                    title = str(embed.get("title", ""))
                    footer = str(embed.get("footer", {}).get("text", ""))
                    if (
                        "How it works" in title
                        or "How it works v1" in footer
                    ):
                        existing = message
                        break
                if existing is not None:
                    break

        if existing is not None:
            message_id = str(existing["id"])
            status, _ = request(
                "PATCH",
                f"/channels/{channel_id}/messages/{message_id}",
                token,
                payload,
            )
            action = "updated"
        else:
            status, message = request(
                "POST", f"/channels/{channel_id}/messages", token, payload
            )
            if status not in {200, 201} or not isinstance(message, dict):
                print(f"post_failed #{name} status={status}")
                continue
            message_id = str(message["id"])
            action = "created"

        if status not in {200, 201}:
            print(f"write_failed #{name} status={status}")
            continue
        posted += 1

        pin_status, _ = request(
            "PUT", f"/channels/{channel_id}/pins/{message_id}", token
        )
        if pin_status == 204:
            pinned += 1
            pin_label = "pinned"
        else:
            pin_label = f"pin_failed({pin_status})"
            pin_blocked.append(name)
        print(
            f"#{name}: {action} message={message_id} {pin_label}"
        )

    print(
        f"summary posted={posted}/{len(CHANNELS)} pinned={pinned}/{len(CHANNELS)}"
    )
    if pin_blocked:
        print(
            "pin_blocked_channels=" + ",".join(pin_blocked)
        )
        print(
            "Grant Manage Messages to the Agent Switch Zasky role and rerun "
            "this script to pin the existing guides."
        )
    return 0 if posted == len(CHANNELS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
