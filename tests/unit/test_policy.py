from __future__ import annotations

from tests.fixtures.identities import OWNER_ID, ROOM_ID, STRANGER_ID
from zasky.access.policy import authorize_message
from zasky.config import Settings
from zasky.switch.events import MessageEvent


def make_event(
    *,
    room_id: str = ROOM_ID,
    sender: str = OWNER_ID,
    addressed: bool = True,
    body: str = "hello",
    sequence: int = 1,
) -> MessageEvent:
    return MessageEvent.model_validate(
        {
            "event": "message",
            "id": sequence,
            "data": {
                "type": "message",
                "room_id": room_id,
                "payload": {
                    "addressed": addressed,
                    "sender": sender,
                    "sender_name": "Owner",
                    "message_id": "m1",
                    "body": body,
                },
                "sequence": sequence,
            },
        }
    )


def test_owner_in_allowed_room_is_allowed(settings: Settings) -> None:
    decision = authorize_message(make_event(), settings)
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_wrong_room_is_rejected(settings: Settings) -> None:
    decision = authorize_message(make_event(room_id="other-room"), settings)
    assert decision.allowed is False
    assert decision.reason == "room_not_allowed"


def test_wrong_sender_is_rejected(settings: Settings) -> None:
    decision = authorize_message(make_event(sender=STRANGER_ID), settings)
    assert decision.allowed is False
    assert decision.reason == "sender_not_owner"


def test_unaddressed_event_is_rejected(settings: Settings) -> None:
    decision = authorize_message(make_event(addressed=False), settings)
    assert decision.allowed is False
    assert decision.reason == "not_addressed"


def test_unaddressed_owner_approval_is_allowed(settings: Settings) -> None:
    for body in ("approve ZK-4F8Q", "yes", "looks good", "lock it in"):
        decision = authorize_message(
            make_event(addressed=False, body=body), settings
        )
        assert decision.allowed is True


def test_empty_body_is_rejected(settings: Settings) -> None:
    decision = authorize_message(make_event(body="   "), settings)
    assert decision.allowed is False
    assert decision.reason == "empty_message"


def test_oversized_body_is_rejected(settings: Settings) -> None:
    small = settings.model_copy(update={"max_message_chars": 5})
    decision = authorize_message(make_event(body="hello world"), small)
    assert decision.allowed is False
    assert decision.reason == "message_too_long"


def test_sandbox_room_allows_judges_but_stays_isolated(settings: Settings) -> None:
    configured = settings.model_copy(
        update={"sandbox_switch_room_id": "sandbox-room-1"}
    )
    decision = authorize_message(
        make_event(room_id="sandbox-room-1", sender=STRANGER_ID),
        configured,
    )
    assert decision.allowed is True
    assert decision.reason == "sandbox"
    unaddressed = authorize_message(
        make_event(
            room_id="sandbox-room-1",
            sender=STRANGER_ID,
            addressed=False,
        ),
        configured,
    )
    assert unaddressed.allowed is True
    agent_kind = make_event(
        room_id="sandbox-room-1", sender="agent-participant", addressed=False
    )
    agent_kind.data.payload.sender_kind = "agent"
    assert authorize_message(agent_kind, configured).reason == "sender_is_agent"
    wrong_sender_main = authorize_message(
        make_event(sender=STRANGER_ID), configured
    )
    assert wrong_sender_main.reason == "sender_not_owner"
