"""Deterministic approval/rejection command parser.

This runs before any model call. Conversational agreement such as "looks
good" is deliberately not an approval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMAND_RE = re.compile(
    r"^(?P<action>approve|reject)(?:\s+(?P<code>ZK-[A-Z0-9]{4}))?$",
    re.IGNORECASE,
)
_CONVERSATIONAL_RE = re.compile(
    r"^(?:looks? (?:good|fine)|sounds? good|lock (?:it|that) in|go ahead|"
    r"yes(?:,? (?:do it|please))?|approved?|okay(?:,? (?:do it|lock it in))?)"
    r"[.!]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ApprovalCommand:
    action: str
    code: str | None


def is_conversational_approval(text: str) -> bool:
    """True for short affirmative phrases that must never commit a proposal."""
    normalized = " ".join(text.strip().split())
    return _CONVERSATIONAL_RE.fullmatch(normalized) is not None


def parse_approval_command(text: str) -> ApprovalCommand | None:
    normalized = " ".join(text.strip().split())
    match = _COMMAND_RE.fullmatch(normalized)
    if match is None:
        return None
    return ApprovalCommand(
        action=match.group("action").lower(),
        code=match.group("code").upper() if match.group("code") else None,
    )
