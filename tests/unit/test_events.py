from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from zasky.switch.events import (
    ConnectionStateFrame,
    decode_frame,
    extract_sequence,
    parse_message_event,
)


def message_frame(sequence: int = 7, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "addressed": True,
        "sender": "@owner:test",
        "sender_name": "Owner",
        "message_id": "message-1",
        "body": "hello",
        "timestamp": 1,
    }
    payload.update(overrides)
    return {
        "event": "message",
        "data": {
            "type": "message",
            "room_id": "room-1",
            "payload": payload,
            "sequence": sequence,
        },
        "id": sequence,
    }


def test_parse_valid_message_event() -> None:
    event = parse_message_event(json.dumps(message_frame()))
    assert event.id == 7
    assert event.data.sequence == 7
    assert event.data.room_id == "room-1"
    assert event.data.payload.addressed is True
    assert event.data.payload.sender == "@owner:test"


def test_parse_message_event_accepts_bytes() -> None:
    event = parse_message_event(json.dumps(message_frame()).encode())
    assert event.data.payload.body == "hello"


def test_missing_payload_is_rejected() -> None:
    raw = json.dumps({"event": "message", "data": {"room_id": "room-1"}, "id": 1})
    with pytest.raises(ValidationError):
        parse_message_event(raw)


def test_non_object_frame_is_rejected() -> None:
    with pytest.raises(ValueError):
        decode_frame("[]")


def test_extract_sequence_prefers_envelope_id() -> None:
    frame = message_frame(sequence=9)
    assert extract_sequence(frame) == 9


def test_extract_sequence_falls_back_to_data_sequence() -> None:
    frame = message_frame(sequence=11)
    frame.pop("id")
    assert extract_sequence(frame) == 11


def test_connection_state_data_shape_parses_without_type() -> None:
    state = ConnectionStateFrame.model_validate(
        {
            "connection_id": "conn-1",
            "agent_id": "agent-1",
            "generation": 7,
            "rooms": ["room-1"],
            "cursor": 3,
            "protocol": 9,
            "heartbeat_interval_seconds": 2,
        }
    )
    assert state.generation == 7
    assert state.rooms == ["room-1"]
    assert state.cursor == 3
