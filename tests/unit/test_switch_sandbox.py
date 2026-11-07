from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from zasky.config import Settings
from zasky.switch.client import SwitchClient
from zasky.switch.events import MessageEvent

SANDBOX_ROOM = "5d628139-0f07-4a10-ae77-321711337a00"


class FakeOps:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def connect_to_room(self, room_id: str) -> dict:
        self.calls.append(("connect", room_id))
        return {"ok": True}

    async def post_message(self, body: str, *, thread_id: str | None = None) -> dict:
        self.calls.append(("post", body))
        return {"ok": True}

    async def close(self) -> None:
        return None


def sandbox_event(room_id: str = SANDBOX_ROOM) -> MessageEvent:
    return MessageEvent.model_validate(
        {
            "event": "message",
            "id": 7,
            "data": {
                "type": "message",
                "room_id": room_id,
                "payload": {
                    "addressed": False,
                    "sender": "@judge:discord",
                    "sender_name": "Judge",
                    "message_id": "m-1",
                    "body": "hello",
                },
                "sequence": 7,
            },
        }
    )


def test_sandbox_subscription_uses_all_filter(settings: Settings) -> None:
    configured = settings.model_copy(
        update={"sandbox_switch_room_id": SANDBOX_ROOM}
    )
    client = SwitchClient(
        configured,
        SimpleNamespace(),  # type: ignore[arg-type]
        FakeOps(),  # type: ignore[arg-type]
    )
    uri = client._build_uri()
    query = parse_qs(urlparse(uri).query)
    assert query["filter"] == ["all"]
    rooms = query["rooms"][0].split(",")
    assert configured.switch_room_id in rooms
    assert SANDBOX_ROOM in rooms


@pytest.mark.asyncio
async def test_sandbox_reply_switches_room_and_restores_main(
    settings: Settings,
) -> None:
    configured = settings.model_copy(
        update={"sandbox_switch_room_id": SANDBOX_ROOM}
    )
    ops = FakeOps()
    client = SwitchClient(
        configured,
        SimpleNamespace(),  # type: ignore[arg-type]
        ops,  # type: ignore[arg-type]
    )
    await client._post_reply("sandbox reply", sandbox_event())
    assert ops.calls == [
        ("connect", SANDBOX_ROOM),
        ("post", "sandbox reply"),
        ("connect", configured.switch_room_id),
    ]
