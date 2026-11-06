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


@dataclass(frozen=True)
class ApprovalCommand:
    action: str
    code: str | None


def parse_approval_command(text: str) -> ApprovalCommand | None:
    normalized = " ".join(text.strip().split())
    match = _COMMAND_RE.fullmatch(normalized)
    if match is None:
        return None
    return ApprovalCommand(
        action=match.group("action").lower(),
        code=match.group("code").upper() if match.group("code") else None,
    )
