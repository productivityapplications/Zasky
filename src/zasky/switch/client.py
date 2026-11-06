"""Switch WebSocket lifecycle and deterministic Phase 1 echo.

The connection loop is deliberately small: it owns transport concerns, the
room/owner gate and the event ledger. It has no planner or model authority.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets
from pydantic import ValidationError

from zasky.access.policy import authorize_message
from zasky.config import Settings
from zasky.storage.database import Database
from zasky.switch.events import (
    ConnectionStateFrame,
    EvictedFrame,
    GapFrame,
    MessageEvent,
    decode_frame,
    extract_sequence,
    parse_message_event,
)
from zasky.switch.operations import SwitchOperations, SwitchOperationsError

logger = logging.getLogger(__name__)


class SwitchProtocolError(RuntimeError):
    """The server refused or contradicted the expected protocol."""


def build_echo_reply(body: str) -> str:
    """Deterministic Phase 1 response. It never echoes private text."""
    return f"Zasky is connected. Phase 1 echo received ({len(body)} characters)."


class SwitchClient:
    """Maintain one Switch connection and process owner-addressed messages."""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        operations: SwitchOperations | None = None,
    ) -> None:
        self._settings = settings
        self._db = database
        self._ops = operations or SwitchOperations(settings)
        self._owns_ops = operations is None

        self._stop = asyncio.Event()
        self._terminal = False
        self._connected = False
        self._room_ready = asyncio.Event()
        self._connected_at: datetime | None = None
        self._last_frame_monotonic: float | None = None

        self._generation: str | None = None
        self._protocol_revision: str | None = None
        self._highest_processed = 0
        self._gap_pending = False

        self._queue: asyncio.Queue[MessageEvent] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._room_init_task: asyncio.Task[None] | None = None
        self._websocket: Any = None

    @property
    def is_connected(self) -> bool:
        if not self._connected or self._last_frame_monotonic is None:
            return False
        # Switch sends a ping every two seconds. Ten seconds is a conservative
        # readiness threshold and avoids flapping on a single missed frame.
        return (time.monotonic() - self._last_frame_monotonic) < 10.0

    @property
    def is_ready(self) -> bool:
        return self.is_connected and self._room_ready.is_set()

    @property
    def connection_status(self) -> str:
        if self._terminal:
            return "terminal"
        if self.is_connected:
            return "connected"
        return "disconnected"

    async def close(self) -> None:
        self._stop.set()
        await self._close_websocket()
        for task in (self._worker_task, self._room_init_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._worker_task = None
        self._room_init_task = None
        if self._owns_ops:
            await self._ops.close()

    async def run(self) -> None:
        """Connect and reconnect until stopped or terminally evicted."""
        state = await self._db.get_connection_state(self._settings.switch_agent_id)
        if state is not None:
            self._highest_processed = state.highest_processed_sequence
            self._generation = state.generation
            self._protocol_revision = state.protocol_revision

        backoff = self._settings.switch_reconnect_min_seconds
        while not self._stop.is_set() and not self._terminal:
            try:
                await self._connect_once()
                backoff = self._settings.switch_reconnect_min_seconds
            except asyncio.CancelledError:
                raise
            except SwitchProtocolError as exc:
                logger.warning(
                    "Switch protocol error",
                    extra={"component": "switch", "error_code": type(exc).__name__},
                )
            except (OSError, TimeoutError, websockets.WebSocketException) as exc:
                logger.warning(
                    "Switch connection lost",
                    extra={"component": "switch", "error_code": type(exc).__name__},
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                logger.exception(
                    "Unexpected Switch loop error",
                    extra={"component": "switch", "error_code": type(exc).__name__},
                )

            if self._stop.is_set() or self._terminal:
                break
            jitter = random.uniform(0.0, backoff * 0.25)
            await asyncio.sleep(backoff + jitter)
            backoff = min(
                backoff * 2.0, self._settings.switch_reconnect_max_seconds
            )

    async def _connect_once(self) -> None:
        uri = self._build_uri()
        async with websockets.connect(
            uri,
            additional_headers={
                "Authorization": (
                    "Bearer "
                    f"{self._settings.switch_agent_api_key.get_secret_value()}"
                )
            },
            ping_interval=None,
            open_timeout=20,
            close_timeout=5,
            max_size=2**22,
        ) as websocket:
            self._websocket = websocket
            self._last_frame_monotonic = time.monotonic()
            self._worker_task = asyncio.create_task(
                self._worker_loop(), name="zasky-event-worker"
            )
            logger.info(
                "Switch socket opened",
                extra={"component": "switch", "connection_status": "connecting"},
            )
            try:
                async for raw in websocket:
                    await self._handle_frame(raw, websocket)
                    if self._terminal:
                        break
            finally:
                self._connected = False
                self._room_ready.clear()
                self._websocket = None
                for task in (self._worker_task, self._room_init_task):
                    if task is not None:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
                self._worker_task = None
                self._room_init_task = None
                self._drain_queue()
                logger.info(
                    "Switch socket closed",
                    extra={"component": "switch", "connection_status": self.connection_status},
                )

    def _build_uri(self) -> str:
        parts = urlsplit(self._settings.resolved_ws_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["connection_id"] = self._settings.switch_connection_id
        query["rooms"] = self._settings.switch_room_id
        query["filter"] = "addressed"
        if self._highest_processed > 0:
            query["start_from"] = str(self._highest_processed)
        if self._generation is not None:
            query["expected_generation"] = self._generation
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    async def _handle_frame(self, raw: str | bytes, websocket: Any) -> None:
        self._last_frame_monotonic = time.monotonic()
        try:
            frame = decode_frame(raw)
        except (ValueError, UnicodeDecodeError):
            logger.warning(
                "Malformed Switch frame",
                extra={"component": "switch", "error_code": "INVALID_FRAME"},
            )
            return

        # The deployed Switch envelope puts both the kind and the fields under
        # `event`/`data`; older descriptions call control kinds `type`. Accept
        # both shapes so a protocol revision cannot silently blind the client.
        event_name = frame.get("event") or frame.get("type")
        raw_data = frame.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else frame

        if event_name == "ping":
            await websocket.send(
                json.dumps({"type": "pong", "cursor": self._highest_processed})
            )
            return
        if event_name == "connection_state":
            await self._handle_connection_state(data)
            return
        if event_name == "gap":
            await self._handle_gap(data)
            return
        if event_name == "evicted":
            await self._handle_evicted(data, websocket)
            return
        if event_name == "refused":
            status = data.get("status")
            logger.error(
                "Switch refused the connection",
                extra={"component": "switch", "error_code": f"REFUSED_{status}"},
            )
            if status in (400, 401, 403):
                self._terminal = True
            return
        if event_name in {"subscription_changed", "room_released"}:
            logger.info(
                "Switch connection membership changed",
                extra={"component": "switch", "connection_status": self.connection_status},
            )
            return
        if event_name == "message":
            try:
                event = parse_message_event(frame)
            except ValidationError:
                sequence = extract_sequence(frame)
                if sequence is not None:
                    await self._db.advance_cursor(
                        agent_id=self._settings.switch_agent_id,
                        connection_id=self._settings.switch_connection_id,
                        sequence=sequence,
                        generation=self._generation,
                        protocol_revision=self._protocol_revision,
                    )
                    self._highest_processed = max(self._highest_processed, sequence)
                logger.warning(
                    "Invalid message event",
                    extra={"component": "switch", "error_code": "INVALID_EVENT"},
                )
                return
            await self._queue.put(event)
            return
        logger.debug("Ignoring unknown Switch frame type")

    async def _handle_connection_state(self, frame: dict[str, Any]) -> None:
        state = ConnectionStateFrame.model_validate(frame)
        if self._settings.switch_room_id not in state.rooms:
            self._terminal = True
            raise SwitchProtocolError("configured room not present in connection_state")

        self._generation = str(state.generation) if state.generation is not None else None
        self._protocol_revision = (
            str(state.protocol) if state.protocol is not None else None
        )
        self._highest_processed = max(self._highest_processed, state.cursor)
        self._connected_at = datetime.now(UTC)
        await self._db.save_connection_state(
            agent_id=self._settings.switch_agent_id,
            connection_id=state.connection_id,
            generation=self._generation,
            protocol_revision=self._protocol_revision,
            cursor=self._highest_processed,
            connected_at=self._connected_at,
        )

        self._connected = True
        self._room_ready.clear()
        self._room_init_task = asyncio.create_task(
            self._initialize_room(), name="zasky-room-init"
        )
        logger.info(
            "Switch connection established; room initialization started",
            extra={"component": "switch", "connection_status": "connecting"},
        )

    async def _initialize_room(self) -> None:
        """Claim/read the room without blocking ping handling."""
        try:
            context = await self._ops.connect_to_room(self._settings.switch_room_id)
        except SwitchOperationsError as exc:
            logger.error(
                "Switch room initialization failed",
                extra={"component": "switch", "error_code": type(exc).__name__},
            )
            await self._close_websocket()
            return
        participants = context.get("participants", [])
        participant_count = len(participants) if isinstance(participants, list) else 0
        self._room_ready.set()
        logger.info(
            "Switch room ready",
            extra={
                "component": "switch",
                "connection_status": "connected",
                "participant_count": participant_count,
            },
        )

    async def _handle_gap(self, frame: dict[str, Any]) -> None:
        gap = GapFrame.model_validate(frame)
        resumed = gap.resumed_at or gap.resumed_position
        if resumed is not None:
            self._highest_processed = max(self._highest_processed, resumed)
            await self._db.advance_cursor(
                agent_id=self._settings.switch_agent_id,
                connection_id=self._settings.switch_connection_id,
                sequence=self._highest_processed,
                generation=self._generation,
                protocol_revision=self._protocol_revision,
            )
        self._gap_pending = True
        logger.warning(
            "Switch gap received; context will be reread before the next reply",
            extra={"component": "switch", "error_code": "SWITCH_GAP"},
        )

    async def _handle_evicted(self, frame: dict[str, Any], websocket: Any) -> None:
        evicted = EvictedFrame.model_validate(frame)
        logger.warning(
            "Switch eviction",
            extra={"component": "switch", "error_code": f"EVICTED_{evicted.code}"},
        )
        if evicted.code == "taken_over":
            self._terminal = True
            self._stop.set()
        await websocket.close()

    async def _worker_loop(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                await self._process_event(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive boundary
                logger.exception(
                    "Event processing failed",
                    extra={"component": "switch", "error_code": type(exc).__name__},
                )
            finally:
                self._queue.task_done()

    async def _process_event(self, event: MessageEvent) -> None:
        sequence = event.data.sequence
        correlation_id = uuid.uuid4().hex
        claim = await self._db.claim_event(
            agent_id=self._settings.switch_agent_id,
            sequence=sequence,
            connection_id=self._settings.switch_connection_id,
            room_id=event.data.room_id,
            sender_id=event.data.payload.sender,
            message_id=event.data.payload.message_id or None,
            correlation_id=correlation_id,
        )
        if not claim.is_new:
            await self._db.advance_cursor(
                agent_id=self._settings.switch_agent_id,
                connection_id=self._settings.switch_connection_id,
                sequence=sequence,
                generation=self._generation,
                protocol_revision=self._protocol_revision,
            )
            self._highest_processed = max(self._highest_processed, sequence)
            logger.info(
                "Duplicate Switch event ignored",
                extra={"component": "switch", "event_sequence": sequence},
            )
            return

        if self._gap_pending:
            try:
                context = await self._ops.read_context(limit=20)
                threads = context.get("threads", [])
                thread_count = len(threads) if isinstance(threads, list) else 0
                logger.info(
                    "Switch context reread after gap",
                    extra={"component": "switch", "thread_count": thread_count},
                )
            except SwitchOperationsError:
                logger.warning(
                    "Context reread after gap failed",
                    extra={"component": "switch", "error_code": "CONTEXT_READ_FAILED"},
                )
            self._gap_pending = False

        decision = authorize_message(event, self._settings)
        if not decision.allowed:
            await self._db.finish_event(
                agent_id=self._settings.switch_agent_id,
                sequence=sequence,
                connection_id=self._settings.switch_connection_id,
                outcome="ignored",
                generation=self._generation,
                protocol_revision=self._protocol_revision,
            )
            self._highest_processed = max(self._highest_processed, sequence)
            logger.info(
                "Inbound event ignored",
                extra={
                    "component": "access",
                    "event_sequence": sequence,
                    "outcome": "ignored",
                    "error_code": decision.reason,
                },
            )
            return

        reply = build_echo_reply(event.data.payload.body)
        outcome = "replied"
        try:
            await asyncio.wait_for(self._room_ready.wait(), timeout=15.0)
            await self._ops.post_message(reply)
        except TimeoutError:
            outcome = "failed"
            logger.error(
                "Reply skipped because the room was not ready",
                extra={
                    "component": "switch",
                    "event_sequence": sequence,
                    "outcome": "failed",
                    "error_code": "ROOM_NOT_READY",
                },
            )
        except SwitchOperationsError as exc:
            outcome = "failed"
            logger.error(
                "Reply post failed",
                extra={
                    "component": "switch",
                    "event_sequence": sequence,
                    "outcome": "failed",
                    "error_code": type(exc).__name__,
                },
            )
        await self._db.finish_event(
            agent_id=self._settings.switch_agent_id,
            sequence=sequence,
            connection_id=self._settings.switch_connection_id,
            outcome=outcome,
            generation=self._generation,
            protocol_revision=self._protocol_revision,
        )
        self._highest_processed = max(self._highest_processed, sequence)
        logger.info(
            "Inbound event processed",
            extra={
                "component": "switch",
                "event_sequence": sequence,
                "outcome": outcome,
            },
        )

    def _drain_queue(self) -> None:
        while not self._queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
                self._queue.task_done()

    async def _close_websocket(self) -> None:
        websocket = self._websocket
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()
