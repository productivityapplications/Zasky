from __future__ import annotations

from zasky.access.approvals import is_conversational_approval, parse_approval_command


def test_exact_commands_still_parse() -> None:
    assert parse_approval_command("approve ZK-4F8Q").code == "ZK-4F8Q"
    assert parse_approval_command("reject ZK-4F8Q").action == "reject"
    assert parse_approval_command("approve").code is None


def test_conversational_approval_is_never_an_exact_command() -> None:
    for phrase in ("looks good", "looks good!", "sounds good", "lock it in",
                   "lock that in", "go ahead", "yes please", "approved"):
        assert is_conversational_approval(phrase) is True
        assert parse_approval_command(phrase) is None


def test_question_is_not_treated_as_approval() -> None:
    assert is_conversational_approval("should I lock that in?") is False
    assert is_conversational_approval("does this look good?") is False
