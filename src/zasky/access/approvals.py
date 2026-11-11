"""Deterministic approval/rejection command parsing.

Exact commands and owner-only conversational affirmations are resolved before
the model runs. A conversational "yes" applies the newest pending proposal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MENTION_PREFIX_RE = re.compile(r"^(?:(?:<@[!&]?\d+>|@[\w.-]+)\s*)+", re.IGNORECASE)
_COMMAND_RE = re.compile(
    r"^(?:please\s+)?(?P<action>approve|reject)"
    r"(?:\s+(?P<code>ZK-[A-Z0-9]{4}))?(?:\s+please)?[.!]*$",
    re.IGNORECASE,
)
_DELEGATE_RE = re.compile(
    r"^delegate\s+(?P<code>ZK-[A-Z0-9]{4})(?:\s+(?P<instructions>.+))?[.!]*$",
    re.IGNORECASE,
)
_APPROVE_EXECUTION_RE = re.compile(
    r"^approve\s+execution\s+(?P<code>ZK-[A-Z0-9]{4})[.!]*$",
    re.IGNORECASE,
)
_CONVERSATIONAL_RE = re.compile(
    r"^(?:looks? (?:good|fine)|sounds? good|that works|perfect|great|"
    r"lock (?:it|that) in|go ahead|go for it|do it|let'?s do it|"
    r"yes(?:,? (?:do it|please|lock it in))?|yeah|yep|sure|"
    r"approved?|approve(?: it)?|"
    r"ok(?:ay)?(?:,? (?:do it|lock it in))?)[.!]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ApprovalCommand:
    action: str
    code: str | None
    instructions: str | None = None


def _normalize_command(text: str) -> str:
    normalized = " ".join(text.strip().split())
    normalized = _MENTION_PREFIX_RE.sub("", normalized).strip()
    normalized = re.sub(r"[`*_]", "", normalized)
    return normalized.strip(" .!?,;:")


def is_conversational_approval(text: str) -> bool:
    """True for short affirmative phrases the deterministic parser accepts."""
    normalized = _normalize_command(text)
    return _CONVERSATIONAL_RE.fullmatch(normalized) is not None


def parse_approval_command(text: str) -> ApprovalCommand | None:
    normalized = _normalize_command(text)
    execution = _APPROVE_EXECUTION_RE.fullmatch(normalized)
    if execution is not None:
        return ApprovalCommand(
            action="approve_execution",
            code=execution.group("code").upper(),
        )
    delegation = _DELEGATE_RE.fullmatch(normalized)
    if delegation is not None:
        instructions = delegation.group("instructions")
        return ApprovalCommand(
            action="delegate",
            code=delegation.group("code").upper(),
            instructions=instructions.strip() if instructions else None,
        )
    match = _COMMAND_RE.fullmatch(normalized)
    if match is not None:
        return ApprovalCommand(
            action=match.group("action").lower(),
            code=match.group("code").upper() if match.group("code") else None,
        )
    if _CONVERSATIONAL_RE.fullmatch(normalized):
        return ApprovalCommand(action="approve", code=None)
    return None
