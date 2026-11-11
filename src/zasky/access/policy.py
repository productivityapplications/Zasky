"""Inbound authorization.

The exact configured room and the exact configured owner participant ID are
checked before any model call, room context read or domain write. Missing or
malformed identity fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass

from zasky.config import Settings
from zasky.switch.events import MessageEvent


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


def authorize_message(event: MessageEvent, settings: Settings) -> AccessDecision:
    """Return whether this inbound event may be processed."""
    data = event.data
    payload = data.payload

    sandbox_room = settings.sandbox_switch_room_id
    is_sandbox = bool(sandbox_room and data.room_id == sandbox_room)
    if data.room_id != settings.switch_room_id and not is_sandbox:
        return AccessDecision(False, "room_not_allowed")

    if not is_sandbox:
        if payload.sender != settings.owner_switch_participant_id:
            return AccessDecision(False, "sender_not_owner")
        # The main room is a private owner room. The owner may speak naturally
        # without an explicit mention; the exact owner and room checks above
        # remain mandatory.
    else:
        # The sandbox is a public judge surface. Discord mention translation is
        # unreliable across bridges, so any human message in this exact room is
        # accepted. Never accept the agent's or a system participant's own
        # message, which would create a reply loop.
        if payload.sender_kind in {"agent", "system"}:
            return AccessDecision(False, "sender_is_agent")
        if payload.sender in {
            settings.switch_agent_id,
            settings.switch_connection_id,
        }:
            return AccessDecision(False, "sender_is_agent")

    body = payload.body
    if not body.strip():
        return AccessDecision(False, "empty_message")
    if len(body) > settings.max_message_chars:
        return AccessDecision(False, "message_too_long")

    return AccessDecision(True, "sandbox" if is_sandbox else "ok")
