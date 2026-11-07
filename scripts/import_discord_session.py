#!/usr/bin/env python3
"""Create a Playwright storage state from exported Discord cookies + token.

The user must place the Discord web token in
/root/Zasky-secrets/discord-token.txt (one line, never in chat). The resulting
storage state is written to /root/Zasky-secrets/discord-storage-state.json with
mode 0600 and is never printed.
"""

from __future__ import annotations

import json
from pathlib import Path

SECRETS = Path("/root/Zasky-secrets")
COOKIES = SECRETS / "discord-cookies.json"
TOKEN = SECRETS / "discord-token.txt"
OUTPUT = SECRETS / "discord-storage-state.json"


def main() -> None:
    if not TOKEN.is_file():
        raise SystemExit(f"Missing token file: {TOKEN}")
    token = TOKEN.read_text().strip()
    if not token:
        raise SystemExit("Discord token file is empty.")
    raw = json.loads(COOKIES.read_text()) if COOKIES.is_file() else []
    same_site = {
        "lax": "Lax",
        "strict": "Strict",
        "no_restriction": "None",
        "unspecified": "Lax",
    }
    cookies = []
    if isinstance(raw, list):
        for cookie in raw:
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
    # Discord stores the token as a JSON-encoded string in localStorage.
    storage_token = token if token.startswith('"') and token.endswith('"') else f'"{token}"'
    state = {
        "cookies": cookies,
        "origins": [
            {
                "origin": "https://discord.com",
                "localStorage": [{"name": "token", "value": storage_token}],
            }
        ],
    }
    OUTPUT.write_text(json.dumps(state, indent=2))
    OUTPUT.chmod(0o600)
    print(f"Wrote {OUTPUT} with {len(cookies)} cookies and a token.")


if __name__ == "__main__":
    main()
