from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
import websockets
from fastapi import FastAPI

from zasky.config import Settings
from zasky.storage.database import Database
from zasky.switch.client import SwitchClient
from zasky.switch.operations import SwitchOperations


class FakeSwitchServer:
    def __init__(self) -> None:
        self.connections: asyncio.Queue[Any] = asyncio.Queue()
        self.active: list[Any] = []
        self.posts: list[str] = []
        self.post_payloads: list[dict[str, Any]] = []
        self.connect_calls = 0
        self.read_context_calls = 0
        self._server: Any = None
        self.port = 0

    async def start(self) -> None:
        self._server = await websockets.serve(
            self._handler, "127.0.0.1", 0, ping_interval=None
        )
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for websocket in list(self.active):
            with contextlib.suppress(Exception):
                await asyncio.wait_for(websocket.close(), timeout=1)
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), timeout=2)

    async def _handler(self, websocket: Any) -> None:
        self.active.append(websocket)
        await self.connections.put(websocket)
        try:
            await websocket.wait_closed()
        finally:
            if websocket in self.active:
                self.active.remove(websocket)

    async def next_connection(self, max_wait: float = 2.0) -> Any:
        return await asyncio.wait_for(self.connections.get(), timeout=max_wait)

    def http_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/agents/{agent_id}/ops/connect_to_room")
        async def connect_to_room() -> dict[str, object]:
            self.connect_calls += 1
            return {
                "result": {
                    "participants": [
                        {"id": "owner-client", "name": "Owner", "type": "user"}
                    ]
                }
            }

        @app.post("/agents/{agent_id}/ops/read_context")
        async def read_context() -> dict[str, object]:
            self.read_context_calls += 1
            return {"result": {"threads": [], "truncated": False}}

        @app.post("/agents/{agent_id}/ops/post_message")
        async def post_message(payload: dict[str, Any]) -> dict[str, object]:
            self.post_payloads.append(dict(payload))
            self.posts.append(str(payload.get("body", "")))
            return {"result": {"event_id": f"posted-{len(self.posts)}"}}

        return app


def message_frame(
    sequence: int,
    *,
    room_id: str = "room-1",
    sender: str = "@owner:test",
    addressed: bool = True,
    body: str = "hello",
    thread_id: str | None = None,
) -> str:
    return json.dumps(
        {
            "event": "message",
            "data": {
                "type": "message",
                "room_id": room_id,
                "payload": {
                    "addressed": addressed,
                    "sender": sender,
                    "sender_name": "Owner",
                    "message_id": f"m{sequence}",
                    "body": body,
                    "thread_id": thread_id,
                    "timestamp": sequence,
                },
                "sequence": sequence,
            },
            "id": sequence,
        }
    )


def connection_state(
    *,
    cursor: int = 0,
    generation: int = 7,
    rooms: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "event": "connection_state",
            "data": {
                "connection_id": "conn-1",
                "agent_id": "agent-1",
                "generation": generation,
                "rooms": rooms or ["room-1"],
                "cursor": cursor,
                "protocol": 9,
                "heartbeat_interval_seconds": 2,
            },
        }
    )


async def wait_until(
    predicate: Callable[[], bool], max_wait: float = 3.0
) -> None:
    deadline = asyncio.get_running_loop().time() + max_wait
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("condition not met")
        await asyncio.sleep(0.01)


async def wait_until_async(
    predicate: Callable[[], Awaitable[bool]], max_wait: float = 3.0
) -> None:
    deadline = asyncio.get_running_loop().time() + max_wait
    while not await predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("condition not met")
        await asyncio.sleep(0.01)


@pytest_asyncio.fixture
async def harness(
    settings: Settings,
    tmp_path: Any,
) -> AsyncIterator[tuple[FakeSwitchServer, SwitchClient, Database, asyncio.Task[None]]]:
    fake = FakeSwitchServer()
    await fake.start()
    http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fake.http_app()),
        base_url="http://switch.test",
    )
    ops = SwitchOperations(settings, client=http_client)
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'zasky-test.db'}")
    await db.init()

    test_settings = settings.model_copy(
        update={
            "switch_ws_url": (
                f"ws://127.0.0.1:{fake.port}/agents/agent-1/connection/ws"
            ),
            "switch_reconnect_min_seconds": 0.05,
            "switch_reconnect_max_seconds": 0.2,
        }
    )
    client = SwitchClient(test_settings, db, ops)
    task = asyncio.create_task(client.run())

    try:
        yield fake, client, db, task
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(client.close(), timeout=3)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(http_client.aclose(), timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(fake.stop(), timeout=4)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(db.close(close_connections=False), timeout=3)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_owner_message_gets_one_echo_and_duplicate_is_ignored(
    harness: tuple[FakeSwitchServer, SwitchClient, Database, asyncio.Task[None]],
) -> None:
    fake, client, db, _task = harness
    websocket = await fake.next_connection()
    await websocket.send(connection_state())
    await wait_until(lambda: client.is_ready)

    await websocket.send(message_frame(1, body="hello"))
    await wait_until(lambda: len(fake.posts) == 1)
    assert fake.posts[0] == "Zasky is connected. Phase 1 echo received (5 characters)."

    async def replied() -> bool:
        return await db.get_event_outcome("agent-1", 1) == "replied"

    await wait_until_async(replied)

    await websocket.send(message_frame(1, body="hello"))
    await asyncio.sleep(0.2)
    assert len(fake.posts) == 1

    await websocket.send(json.dumps({"event": "ping", "data": {}}))
    pong = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
    assert pong["type"] == "pong"
    assert pong["cursor"] >= 1


@pytest.mark.asyncio
async def test_wrong_room_sender_and_unaddressed_are_ignored(
    harness: tuple[FakeSwitchServer, SwitchClient, Database, asyncio.Task[None]],
) -> None:
    fake, client, db, _task = harness
    websocket = await fake.next_connection()
    await websocket.send(connection_state())
    await wait_until(lambda: client.is_ready)

    await websocket.send(message_frame(1, room_id="other-room"))
    await websocket.send(message_frame(2, sender="@stranger:test"))
    await websocket.send(message_frame(3, addressed=False))

    async def all_ignored() -> bool:
        outcomes = [
            await db.get_event_outcome("agent-1", sequence)
            for sequence in (1, 2, 3)
        ]
        return outcomes == ["ignored", "ignored", "ignored"]

    await wait_until_async(all_ignored)
    assert fake.posts == []


@pytest.mark.asyncio
async def test_gap_rereads_context_before_reply(
    harness: tuple[FakeSwitchServer, SwitchClient, Database, asyncio.Task[None]],
) -> None:
    fake, client, db, _task = harness
    websocket = await fake.next_connection()
    await websocket.send(connection_state())
    await wait_until(lambda: client.is_ready)

    await websocket.send(
        json.dumps(
            {
                "event": "gap",
                "data": {
                    "from_sequence": 0,
                    "resumed_at": 1,
                    "resumed_position": {"s": 1},
                    "rooms": ["room-1"],
                    "all_rooms": False,
                    "reason": "test",
                },
            }
        )
    )
    await websocket.send(message_frame(2, body="after gap"))
    await wait_until(lambda: len(fake.posts) == 1)
    assert fake.read_context_calls == 1
    assert "9 characters" in fake.posts[0]

    async def replied() -> bool:
        return await db.get_event_outcome("agent-1", 2) == "replied"

    await wait_until_async(replied)


@pytest.mark.asyncio
async def test_reconnect_resumes_with_cursor_and_generation(
    harness: tuple[FakeSwitchServer, SwitchClient, Database, asyncio.Task[None]],
) -> None:
    fake, client, _db, _task = harness
    websocket = await fake.next_connection()
    await websocket.send(connection_state(cursor=0, generation=7))
    await wait_until(lambda: client.is_ready)

    await websocket.send(message_frame(1, body="hello"))
    await wait_until(lambda: len(fake.posts) == 1)

    async def replied() -> bool:
        return await _db.get_event_outcome("agent-1", 1) == "replied"

    await wait_until_async(replied)
    await websocket.close()

    second = await fake.next_connection()
    query = parse_qs(urlsplit(second.request.path).query)
    assert query["connection_id"] == ["conn-1"]
    assert query["start_from"] == ["1"]
    assert query["expected_generation"] == ["7"]


@pytest.mark.asyncio
async def test_taken_over_is_terminal(
    harness: tuple[FakeSwitchServer, SwitchClient, Database, asyncio.Task[None]],
) -> None:
    fake, client, _db, task = harness
    websocket = await fake.next_connection()
    await websocket.send(connection_state())
    await wait_until(lambda: client.is_ready)

    await websocket.send(
        json.dumps(
            {"event": "evicted", "data": {"code": "taken_over", "reason": "test"}}
        )
    )
    await wait_until(lambda: client.connection_status == "terminal")
    await asyncio.sleep(0.3)
    assert task.done()


@pytest.mark.asyncio
async def test_reply_stays_in_existing_thread(harness) -> None:
    fake, client, _db, _task = harness
    websocket = await fake.next_connection()
    await websocket.send(connection_state())
    await wait_until(lambda: client.is_ready)
    await websocket.send(
        message_frame(1, body="help me with this task", thread_id="thread-1")
    )
    await wait_until(lambda: len(fake.posts) == 1)
    assert fake.post_payloads[0]["thread_id"] == "thread-1"


@pytest.mark.asyncio
async def test_approval_command_bypasses_message_handler(tmp_path, settings: Settings) -> None:
    fake = FakeSwitchServer()
    await fake.start()
    http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fake.http_app()),
        base_url="http://switch.test",
    )
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'approval.db'}")
    await db.init()
    calls: list[tuple[str, str]] = []

    async def message_handler(event):
        calls.append(("message", event.data.payload.body))
        return "model path"

    async def approval_handler(command, event):
        calls.append(("approval", command.code or "none"))
        return ("Approved ZK-ABCD. No further changes.", "approval_applied")

    test_settings = settings.model_copy(
        update={
            "switch_ws_url": f"ws://127.0.0.1:{fake.port}/agents/agent-1/connection/ws",
            "switch_reconnect_min_seconds": 0.05,
            "switch_reconnect_max_seconds": 0.2,
        }
    )
    client = SwitchClient(
        test_settings,
        db,
        SwitchOperations(test_settings, client=http_client),
        message_handler=message_handler,
        approval_handler=approval_handler,
    )
    task = asyncio.create_task(client.run())
    try:
        websocket = await fake.next_connection()
        await websocket.send(connection_state())
        await wait_until(lambda: client.is_ready)
        await websocket.send(message_frame(1, body="approve ZK-ABCD"))
        await wait_until(lambda: len(calls) == 1)
        await wait_until(lambda: len(fake.posts) == 1)

        assert calls == [("approval", "ZK-ABCD")]
        assert fake.posts[0].startswith("Approved ZK-ABCD")
        assert await db.get_event_outcome("agent-1", 1) == "approval_applied"
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(client.close(), timeout=3)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(http_client.aclose(), timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(fake.stop(), timeout=4)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(db.close(close_connections=False), timeout=3)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_unauthorized_events_never_reach_message_handler(
    tmp_path, settings: Settings
) -> None:
    fake = FakeSwitchServer()
    await fake.start()
    http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fake.http_app()),
        base_url="http://switch.test",
    )
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'unauthorized.db'}")
    await db.init()
    calls: list[str] = []

    async def message_handler(event):
        calls.append(event.data.payload.body)
        return "must not run"

    test_settings = settings.model_copy(
        update={
            "switch_ws_url": f"ws://127.0.0.1:{fake.port}/agents/agent-1/connection/ws",
            "switch_reconnect_min_seconds": 0.05,
            "switch_reconnect_max_seconds": 0.2,
        }
    )
    client = SwitchClient(
        test_settings,
        db,
        SwitchOperations(test_settings, client=http_client),
        message_handler=message_handler,
    )
    task = asyncio.create_task(client.run())
    try:
        websocket = await fake.next_connection()
        await websocket.send(connection_state())
        await wait_until(lambda: client.is_ready)
        await websocket.send(message_frame(1, room_id="other-room"))
        await websocket.send(message_frame(2, sender="@stranger:test"))
        await websocket.send(message_frame(3, addressed=False))
        await asyncio.sleep(0.3)
        assert calls == []
        assert fake.posts == []
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(client.close(), timeout=3)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(http_client.aclose(), timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(fake.stop(), timeout=4)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(db.close(close_connections=False), timeout=3)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_typing_placeholder_precedes_final_reply(tmp_path, settings: Settings) -> None:
    fake = FakeSwitchServer()
    await fake.start()
    http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fake.http_app()),
        base_url="http://switch.test",
    )
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'typing.db'}")
    await db.init()

    async def message_handler(event):
        return "Final answer"

    test_settings = settings.model_copy(
        update={
            "switch_ws_url": f"ws://127.0.0.1:{fake.port}/agents/agent-1/connection/ws",
            "switch_reconnect_min_seconds": 0.05,
            "switch_reconnect_max_seconds": 0.2,
        }
    )
    client = SwitchClient(
        test_settings,
        db,
        SwitchOperations(test_settings, client=http_client),
        message_handler=message_handler,
        typing_placeholder=True,
    )
    task = asyncio.create_task(client.run())
    try:
        websocket = await fake.next_connection()
        await websocket.send(connection_state())
        await wait_until(lambda: client.is_ready)
        await websocket.send(message_frame(1, body="What is my plan?"))
        await wait_until(lambda: len(fake.posts) == 2)
        assert fake.posts[0] == "…"
        assert fake.posts[1] == "Final answer"
        assert fake.post_payloads[0].get("thread_id") is None
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(client.close(), timeout=3)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(http_client.aclose(), timeout=3)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(fake.stop(), timeout=4)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(db.close(close_connections=False), timeout=3)
        await asyncio.sleep(0.2)
