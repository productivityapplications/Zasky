"""Run the real model against the synthetic demo DB and capture a transcript.

This is an honest local protocol/transcript demo: it exercises the real
OpenRouter model, the seven tools, the domain service and approval parser. It
does not pretend to capture the Discord UI.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path

from zasky.agent.context import ContextBuilder
from zasky.agent.orchestrator import AgentOrchestrator
from zasky.config import load_settings
from zasky.domain.service import DomainService
from zasky.integrations.openrouter.client import OpenRouterClient
from zasky.integrations.openrouter.usage import CostGuard
from zasky.storage.database import Database
from zasky.switch.events import MessageEvent

OWNER = "@owner:demo"
ROOM = "room-demo"
OUT = Path("artifacts/demo/transcript.txt")


def event(body: str, sequence: int) -> MessageEvent:
    return MessageEvent.model_validate(
        {
            "event": "message",
            "id": sequence,
            "data": {
                "type": "message",
                "room_id": ROOM,
                "payload": {
                    "addressed": True,
                    "sender": OWNER,
                    "sender_name": "Owner",
                    "message_id": f"demo-{sequence}",
                    "body": body,
                    "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                },
                "sequence": sequence,
            },
        }
    )


async def main() -> None:
    settings = load_settings("/root/Zasky-secrets/zasky.env").model_copy(
        update={"database_url": "sqlite+aiosqlite:////root/Zasky/data/demo.db"}
    )
    db = Database(settings.database_url)
    domain = DomainService(db, settings)
    llm = OpenRouterClient(settings)
    orchestrator = AgentOrchestrator(
        settings,
        domain,
        llm,
        ContextBuilder(db, settings),
        CostGuard(db, settings),
    )
    transcript: list[str] = [
        "ZASKY — local protocol/transcript demo",
        "Synthetic data only. Model: openai/gpt-4o-mini via OpenRouter.",
        "The Discord UI is not captured; this shows the real model, tools and approvals.",
        "",
    ]
    try:
        messages = [
            "What's my plan for Friday?",
            (
                "Back. A two-hour call ran over; it's 4pm on Friday, "
                "6 November 2026 (2026-11-06T16:00:00+01:00)."
            ),
        ]
        sequence = 1
        for message in messages:
            transcript.append(f"OWNER: {message}")
            reply = await orchestrator.handle_message(event(message, sequence))
            transcript.append(f"ZASKY: {reply}")
            transcript.append("")
            codes = re.findall(r"ZK-[A-Z0-9]{4}", reply)
            for code in dict.fromkeys(codes):
                transcript.append(f"OWNER: approve {code}")
                result = await domain.resolve_proposal(
                    action="approve",
                    code=code,
                    actor_id=OWNER,
                    room_id=ROOM,
                )
                if result.get("status") == "approved":
                    transcript.append(
                        f"ZASKY: Approved {code}. The change is now stored."
                    )
                else:
                    transcript.append(f"ZASKY: {result.get('status', 'resolved')} {code}.")
                transcript.append("")
            sequence += 1

        follow_up = "What's left this week?"
        transcript.append(f"OWNER: {follow_up}")
        reply = await orchestrator.handle_message(event(follow_up, sequence))
        transcript.append(f"ZASKY: {reply}")
        transcript.append("")
        transcript.append(
            "CLOSING: Zasky doesn't give me discipline. It makes coming back cheap."
        )
        transcript.append("")
    finally:
        await llm.close()
        await db.close(close_connections=False)

    await asyncio.to_thread(OUT.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(
        OUT.write_text, "\n".join(transcript).strip() + "\n", encoding="utf-8"
    )
    print("\n".join(transcript))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
