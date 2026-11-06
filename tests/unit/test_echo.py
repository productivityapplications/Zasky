from __future__ import annotations

from zasky.switch.client import build_echo_reply


def test_echo_reports_length_without_repeating_text() -> None:
    reply = build_echo_reply("private planning note")
    assert "21 characters" in reply
    assert "private planning note" not in reply


def test_echo_is_deterministic() -> None:
    assert build_echo_reply("hello") == build_echo_reply("hello")
