from __future__ import annotations

from zasky.access.approvals import is_conversational_approval, parse_approval_command


def test_exact_commands_still_parse() -> None:
    assert parse_approval_command("approve ZK-4F8Q").code == "ZK-4F8Q"
    assert parse_approval_command("reject ZK-4F8Q").action == "reject"
    assert parse_approval_command("approve").code is None


def test_exact_command_survives_mentions_and_punctuation() -> None:
    command = parse_approval_command("@zasky approve ZK-5HLB.")
    assert command is not None
    assert command.action == "approve"
    assert command.code == "ZK-5HLB"
    command = parse_approval_command("<@&1568193437357056022> approve ZK-T8PX")
    assert command is not None
    assert command.code == "ZK-T8PX"
    command = parse_approval_command("please approve ZK-5HLB please")
    assert command is not None
    assert command.code == "ZK-5HLB"


def test_delegation_and_execution_commands_parse() -> None:
    delegated = parse_approval_command("delegate ZK-4F8Q")
    assert delegated is not None
    assert delegated.action == "delegate"
    assert delegated.code == "ZK-4F8Q"
    approved = parse_approval_command("approve execution ZK-9K2M")
    assert approved is not None
    assert approved.action == "approve_execution"
    assert approved.code == "ZK-9K2M"
    instructed = parse_approval_command(
        "delegate ZK-4F8Q Tell the agent to use a casual tone"
    )
    assert instructed is not None
    assert instructed.action == "delegate"
    assert instructed.code == "ZK-4F8Q"
    assert instructed.instructions == "Tell the agent to use a casual tone"
    assert parse_approval_command("delegate") is None
    assert parse_approval_command("approve execution") is None


def test_conversational_approval_targets_latest_pending_proposal() -> None:
    for phrase in (
        "looks good",
        "looks good!",
        "sounds good",
        "lock it in",
        "lock that in",
        "go ahead",
        "go for it",
        "do it",
        "let's do it",
        "yes",
        "yes please",
        "yes, do it",
        "yeah",
        "sure",
        "okay",
        "perfect",
        "approved",
        "approve it",
    ):
        assert is_conversational_approval(phrase) is True
        command = parse_approval_command(phrase)
        assert command is not None
        assert command.action == "approve"
        assert command.code is None


def test_question_or_edit_sentence_is_not_an_approval() -> None:
    assert is_conversational_approval("should I lock that in?") is False
    assert is_conversational_approval("does this look good?") is False
    assert parse_approval_command("should I lock that in?") is None
    assert (
        parse_approval_command(
            "leave estimated total minutes blank. Approve ZK-5HLB"
        )
        is None
    )
    assert parse_approval_command("yes, change the deadline") is None
