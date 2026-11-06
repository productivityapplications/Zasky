from __future__ import annotations

import pytest
from pydantic import ValidationError

from zasky.config import Settings


def test_resolved_ws_url_is_derived(settings: Settings) -> None:
    assert (
        settings.resolved_ws_url
        == "ws://switch.test/agents/agent-1/connection/ws"
    )


def test_https_base_uses_wss(settings: Settings) -> None:
    secure = settings.model_copy(update={"switch_base_url": "https://switch.test"})
    assert secure.resolved_ws_url.startswith("wss://")


def test_explicit_ws_override_wins(settings: Settings) -> None:
    override = settings.model_copy(
        update={"switch_ws_url": "ws://127.0.0.1:9000/custom"}
    )
    assert override.resolved_ws_url == "ws://127.0.0.1:9000/custom"


def test_base_url_with_path_is_rejected(settings: Settings) -> None:
    data = settings.model_dump()
    data["switch_base_url"] = "http://switch.test/gateway"
    with pytest.raises(ValidationError):
        Settings(**data)


def test_credentials_in_base_url_are_rejected(settings: Settings) -> None:
    data = settings.model_dump()
    data["switch_base_url"] = "http://user:pass@switch.test"
    with pytest.raises(ValidationError):
        Settings(**data)


def test_safe_summary_has_no_secret_or_private_ids(settings: Settings) -> None:
    summary = settings.safe_summary()
    text = repr(summary)
    assert "test-api-key" not in text
    assert "room-1" not in text
    assert "@owner:test" not in text
    assert summary["app_env"] == "test"


def test_invalid_timezone_is_rejected(settings: Settings) -> None:
    data = settings.model_dump()
    data["timezone"] = "Mars/Olympus_Mons"
    with pytest.raises(ValidationError):
        Settings(**data)


def test_daily_limit_is_fixed_at_three(settings: Settings) -> None:
    data = settings.model_dump()
    data["daily_task_limit"] = 2
    with pytest.raises(ValidationError):
        Settings(**data)


def test_week_start_must_be_a_weekday(settings: Settings) -> None:
    data = settings.model_dump()
    data["week_start_day"] = "funday"
    with pytest.raises(ValidationError):
        Settings(**data)


def test_availability_overlap_is_rejected(settings: Settings) -> None:
    data = settings.model_dump()
    data["weekly_availability_json"] = (
        '{"monday": [{"start": "09:00", "end": "12:00"}, '
        '{"start": "11:00", "end": "13:00"}]}'
    )
    with pytest.raises(ValidationError):
        Settings(**data)


def test_availability_accepts_valid_windows(settings: Settings) -> None:
    data = settings.model_dump()
    data["weekly_availability_json"] = (
        '{"monday": [{"start": "09:00", "end": "12:00"}, '
        '{"start": "13:00", "end": "17:00"}]}'
    )
    parsed = Settings(**data)
    assert "monday" in parsed.weekly_availability_json
