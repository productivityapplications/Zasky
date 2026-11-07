#!/usr/bin/env python3
"""Record the Zasky hackathon demo with Playwright.

Requires a logged-in Discord Playwright storage state at
/root/Zasky-secrets/discord-storage-state.json (preferred) or a cookie list at
/root/Zasky-secrets/discord-cookies.json.

The cookie list alone usually cannot authenticate Discord because Discord keeps
the session token in localStorage. The script fails clearly instead of recording
a login screen.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = "/root/Zasky-secrets/zasky.env"
COOKIE_FILE = "/root/Zasky-secrets/discord-cookies.json"
STORAGE_FILE = "/root/Zasky-secrets/discord-storage-state.json"
DEFAULT_DASHBOARD = "https://zasky-flax.vercel.app"
OUTPUT = REPO_ROOT / "artifacts" / "demo" / "raw_video.webm"
CHROME = "/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def storage_state(path: str) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.is_file():
        raise RuntimeError(f"Discord storage state not found: {candidate}")
    data = json.loads(candidate.read_text())
    if isinstance(data, dict) and "cookies" in data:
        return data
    if not isinstance(data, list):
        raise RuntimeError("Discord cookie file has an unsupported shape.")
    same_site = {
        "lax": "Lax",
        "strict": "Strict",
        "no_restriction": "None",
        "unspecified": "Lax",
    }
    cookies = []
    for cookie in data:
        if not isinstance(cookie, dict):
            continue
        expires = cookie.get("expirationDate")
        cookies.append(
            {
                "name": str(cookie.get("name", "")),
                "value": str(cookie.get("value", "")),
                "domain": str(cookie.get("domain", ".discord.com")),
                "path": str(cookie.get("path", "/")),
                "expires": float(expires) if expires else -1,
                "httpOnly": bool(cookie.get("httpOnly")),
                "secure": bool(cookie.get("secure")),
                "sameSite": same_site.get(
                    str(cookie.get("sameSite", "lax")).lower(), "Lax"
                ),
            }
        )
    return {"cookies": cookies, "origins": []}


def wait_for_discord(page: Page) -> None:
    page.goto("https://discord.com/app", wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(5_000)
    if "login" in page.url.lower() or page.locator(
        'button:has-text("Log In")'
    ).count():
        raise RuntimeError(
            "Discord session is not authenticated. The cookie file contains "
            "only tracking/Cloudflare cookies; Discord needs a token-bearing "
            "Playwright storage state."
        )


def textbox(page: Page):
    boxes = page.locator('div[role="textbox"][contenteditable="true"]')
    if boxes.count() == 0:
        boxes = page.locator('div[role="textbox"]')
    if boxes.count() == 0:
        raise RuntimeError("Could not find the Discord message box.")
    return boxes.last


def send(page: Page, text: str, *, mention: bool = True) -> None:
    box = textbox(page)
    box.click()
    page.wait_for_timeout(250)
    if mention:
        page.keyboard.type("@zasky")
        page.wait_for_timeout(1_200)
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
    page.keyboard.type(text)
    page.keyboard.press("Enter")


def find_code(page: Page, prefix: str, timeout: int = 25) -> str | None:
    pattern = re.compile(rf"{re.escape(prefix)} (ZK-[A-Z0-9]{{4}})")
    deadline = time.time() + timeout
    while time.time() < deadline:
        match = pattern.search(page.locator("body").inner_text())
        if match:
            return match.group(1)
        page.wait_for_timeout(800)
    return None


def goto_channel(page: Page, guild: str, channel: str) -> None:
    page.goto(
        f"https://discord.com/channels/{guild}/{channel}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    page.wait_for_timeout(3_000)


def record(args: argparse.Namespace) -> None:
    load_env(Path(args.env_file))
    guild = os.environ.get("DISCORD_GUILD_ID", "").strip()
    control = os.environ.get("DISCORD_CONTROL_CHANNEL_ID", "").strip()
    workspace = os.environ.get("DISCORD_AI_WORKSPACE_CHANNEL_ID", "").strip()
    if not guild or not control or not workspace:
        raise RuntimeError(
            "DISCORD_GUILD_ID, DISCORD_CONTROL_CHANNEL_ID and "
            "DISCORD_AI_WORKSPACE_CHANNEL_ID are required."
        )
    dashboard = (
        args.dashboard_url
        or os.environ.get("VERCEL_DASHBOARD_URL", "")
        or DEFAULT_DASHBOARD
    )
    state_path = args.storage_state or (
        STORAGE_FILE if Path(STORAGE_FILE).is_file() else COOKIE_FILE
    )
    state = storage_state(state_path)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            storage_state=state,
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        wait_for_discord(page)
        print("Discord session authenticated.")

        with page.screencast.start(
            path=str(OUTPUT),
            fps=30,
            size={"width": 1920, "height": 1080},
        ):
            page.goto(dashboard, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(4_000)
            page.mouse.wheel(0, 500)
            page.wait_for_timeout(1_000)

            goto_channel(page, guild, control)
            send(page, "What is my plan for tomorrow? Battery medium.")
            page.wait_for_timeout(6_000)
            page.screenshot(path=str(OUTPUT.parent / "control-plan.png"))

            send(page, "I can't finish the demo script.")
            page.wait_for_timeout(4_000)
            code = find_code(page, "delegate")
            if code:
                print(f"Delegation code: {code}")
                send(page, f"delegate {code}")
                page.wait_for_timeout(6_000)
                page.screenshot(path=str(OUTPUT.parent / "control-delegate.png"))
            else:
                print("Delegation code did not appear; continuing recording.")

            goto_channel(page, guild, workspace)
            page.wait_for_timeout(5_000)
            page.screenshot(path=str(OUTPUT.parent / "ai-workspace.png"))

            goto_channel(page, guild, control)
            send(page, "Back. A 2-hour call ran over, it's 4pm.")
            page.wait_for_timeout(6_000)
            page.screenshot(path=str(OUTPUT.parent / "control-reconcile.png"))

        context.close()
        browser.close()
    if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
        raise RuntimeError("Playwright did not produce a raw video.")
    print(f"Raw video: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=DEFAULT_ENV)
    parser.add_argument("--dashboard-url", default="")
    parser.add_argument("--storage-state", default="")
    args = parser.parse_args()
    try:
        record(args)
    except Exception as exc:
        print(f"RECORDING ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
