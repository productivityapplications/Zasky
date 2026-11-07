"""Typed Switch WebSocket frames.

Only the fields Zasky needs are modelled. Unknown fields are ignored so a
newer Switch server can add metadata without breaking the client.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    addressed: bool
    sender: str = Field(min_length=1)
    sender_name: str = ""
    sender_kind: str | None = None
    message_id: str = ""
    body: str = ""
    timestamp: int | None = None
    thread_id: str | None = None


class MessageEventData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "message"
    room_id: str = Field(min_length=1)
    bridge_id: str | None = None
    channel_type: str | None = None
    payload: MessagePayload
    sequence: int = Field(ge=0)


class MessageEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event: Literal["message"]
    data: MessageEventData
    id: int = Field(ge=0)


class ConnectionStateFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["connection_state"] = "connection_state"
    connection_id: str
    agent_id: str
    generation: str | int | None = None
    scope: str | None = None
    filter: str | None = None
    spawn_capable: bool | None = None
    rooms: list[str] = Field(default_factory=list)
    cursor: int = Field(default=0, ge=0)
    protocol: str | int | None = None
    heartbeat_interval_seconds: float = Field(default=2.0, gt=0)
    server: dict[str, Any] | None = None


class GapFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["gap"] = "gap"
    from_sequence: int | None = None
    resumed_at: int | None = None
    resumed_position: dict[str, int] | None = None
    rooms: list[str] = Field(default_factory=list)
    all_rooms: bool = False
    reason: str | None = None


class EvictedFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["evicted"] = "evicted"
    code: str
    reason: str | None = None


def decode_frame(raw: str | bytes) -> dict[str, Any]:
    """Decode a WebSocket text/binary frame into a JSON object.

    Raises ``ValueError`` for non-object or non-JSON payloads.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("frame is not a JSON object")
    return value


def parse_message_event(raw: str | bytes | dict[str, Any]) -> MessageEvent:
    """Parse a domain ``message`` event; raises ``ValueError`` if invalid."""
    value = raw if isinstance(raw, dict) else decode_frame(raw)
    return MessageEvent.model_validate(value)


def extract_sequence(frame: dict[str, Any]) -> int | None:
    """Best-effort numeric sequence from a domain event frame."""
    candidate = frame.get("id")
    if isinstance(candidate, int) and candidate >= 0:
        return candidate
    data = frame.get("data")
    if isinstance(data, dict):
        sequence = data.get("sequence")
        if isinstance(sequence, int) and sequence >= 0:
            return sequence
    return None
