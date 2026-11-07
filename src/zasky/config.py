"""Validated runtime configuration.

Secrets are represented as :class:`~pydantic.SecretStr` so accidental repr or
logging cannot expose them. Validation errors are reported by field name only
in the CLI, never by value.
"""

from __future__ import annotations

import json
import os
from datetime import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunparse, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEEKDAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


def normalize_database_url(value: str) -> str:
    """Normalize Neon/Postgres URLs for the async asyncpg driver."""
    url = value.strip()
    if not (url.startswith("postgres://") or url.startswith("postgresql://")):
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    # asyncpg uses `ssl=require`, and does not accept libpq's channel_binding.
    parsed = urlsplit(url)
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "channel_binding":
            continue
        if key == "sslmode":
            key = "ssl"
        query.append((key, value))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _parse_hhmm(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 2:
        raise ValueError("time must be HH:MM")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise ValueError("time must be HH:MM") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time must be between 00:00 and 23:59")
    return time(hour, minute)


class Settings(BaseSettings):
    """All Phase 1 runtime settings."""

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
        validate_assignment=True,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./data/zasky.db"

    switch_base_url: str
    switch_agent_id: str
    switch_agent_api_key: SecretStr
    switch_connection_id: str
    switch_room_id: str
    owner_switch_participant_id: str

    # Optional explicit WebSocket URL. Normally derived from the HTTP base URL.
    switch_ws_url: str | None = None

    health_bind_host: str = "127.0.0.1"
    health_bind_port: int = Field(default=8099, ge=1, le=65535)
    max_message_chars: int = Field(default=8000, ge=1, le=8000)

    switch_reconnect_min_seconds: float = Field(default=1.0, ge=0.05, le=60.0)
    switch_reconnect_max_seconds: float = Field(default=30.0, ge=0.1, le=300.0)

    # LLM provider. The operator explicitly selected OpenRouter's
    # OpenAI-compatible Chat Completions endpoint.
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_model: str = "openai/gpt-4o-mini"
    openai_store: bool = False
    openai_max_input_tokens: int = Field(default=24000, ge=1, le=200000)
    openai_max_output_tokens: int = Field(default=600, ge=1, le=32000)
    max_llm_requests_per_day: int = Field(default=100, ge=1, le=10000)
    max_llm_spend_usd_month: float = Field(default=20.0, gt=0, le=10000)
    openai_input_usd_per_1m: float = Field(default=0.15, ge=0)
    openai_output_usd_per_1m: float = Field(default=0.60, ge=0)
    openai_price_effective_date: str = "2026-11-06"
    llm_max_tool_cycles: int = Field(default=5, ge=1, le=5)
    llm_max_proposals_per_message: int = Field(default=2, ge=1, le=2)
    llm_request_timeout_seconds: float = Field(default=60.0, ge=5, le=120)
    typing_placeholder_enabled: bool = True

    # Outbound Discord notification channels. These are application-only
    # destinations; the conversational interface remains Switch. The token is
    # the Discord bot token already used by the Switch bridge.
    discord_bot_token: SecretStr | None = None
    discord_api_base_url: str = "https://discord.com/api/v10"
    discord_daily_briefings_channel_id: str | None = None
    discord_reconcile_alerts_channel_id: str | None = None
    discord_ai_workspace_channel_id: str | None = None
    discord_control_channel_id: str | None = None
    discord_dashboard_sync_channel_id: str | None = None

    # Calendar integration. CALENDAR_FEED_TOKEN permits read-only calendar
    # subscription URLs; dashboard bearer auth always works.
    calendar_feed_token: SecretStr | None = None
    calendar_alarm_minutes: int = Field(default=5, ge=0, le=120)

    # Owner dashboard API (Vercel). The token is mandatory; the public API is
    # never unauthenticated even though CORS is permissive for the demo.
    dashboard_bind_host: str = "0.0.0.0"
    dashboard_port: int = Field(default=8100, ge=1, le=65535)
    dashboard_api_key: SecretStr | None = None
    dashboard_cors_origins: str = "*"

    # Planning profile. Defaults are safe staging values; the operator confirms
    # or overrides them during intake.
    timezone: str = "Africa/Lagos"
    capacity_pct: int = Field(default=65, ge=60, le=70)
    week_start_day: str = "monday"
    daily_task_limit: int = Field(default=3, ge=1, le=3)
    transition_buffer_min: int = Field(default=10, ge=0)
    morning_prep_min: int = Field(default=30, ge=0)
    commute_buffer_min: int = Field(default=0, ge=0)
    weekly_availability_json: str = "{}"
    morning_prompt_time: str = "07:00"
    evening_prompt_time: str = "20:00"
    reminders_enabled: bool = False
    timebox_checkins_enabled: bool = False

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        normalized = value.strip().upper()
        if normalized not in allowed:
            raise ValueError("must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG")
        return normalized

    @field_validator("database_url")
    @classmethod
    def _valid_database_url(cls, value: str) -> str:
        normalized = normalize_database_url(value)
        if not (
            normalized.startswith("sqlite+aiosqlite:///")
            or normalized.startswith("postgresql+asyncpg://")
        ):
            raise ValueError(
                "must use sqlite+aiosqlite:/// or postgresql+asyncpg://"
            )
        return normalized

    @field_validator("switch_base_url")
    @classmethod
    def _valid_base_url(cls, value: str) -> str:
        candidate = value.strip().rstrip("/")
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("must use http:// or https://")
        if not parsed.netloc:
            raise ValueError("must include a host")
        if parsed.username or parsed.password:
            raise ValueError("must not embed credentials")
        if parsed.path not in {"", "/"}:
            raise ValueError("must not include a path")
        if parsed.query or parsed.fragment:
            raise ValueError("must not include a query or fragment")
        return candidate

    @field_validator("switch_ws_url")
    @classmethod
    def _valid_ws_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        parsed = urlparse(candidate)
        if parsed.scheme not in {"ws", "wss"}:
            raise ValueError("must use ws:// or wss://")
        if not parsed.netloc:
            raise ValueError("must include a host")
        if parsed.username or parsed.password:
            raise ValueError("must not embed credentials")
        return candidate

    @field_validator(
        "switch_agent_id",
        "switch_connection_id",
        "switch_room_id",
        "owner_switch_participant_id",
    )
    @classmethod
    def _non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("openai_base_url")
    @classmethod
    def _valid_llm_base_url(cls, value: str) -> str:
        candidate = value.strip().rstrip("/")
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("must use http:// or https://")
        if not parsed.netloc:
            raise ValueError("must include a host")
        if parsed.username or parsed.password:
            raise ValueError("must not embed credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("must not include a query or fragment")
        return candidate

    @field_validator("discord_api_base_url")
    @classmethod
    def _valid_discord_api_base(cls, value: str) -> str:
        candidate = value.strip().rstrip("/")
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("must use http:// or https://")
        if not parsed.netloc:
            raise ValueError("must include a host")
        if parsed.username or parsed.password:
            raise ValueError("must not embed credentials")
        return candidate

    @field_validator(
        "discord_daily_briefings_channel_id",
        "discord_reconcile_alerts_channel_id",
        "discord_ai_workspace_channel_id",
        "discord_control_channel_id",
        "discord_dashboard_sync_channel_id",
    )
    @classmethod
    def _valid_discord_channel_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not cleaned.isdigit() or len(cleaned) < 15:
            raise ValueError("must be a Discord snowflake channel ID")
        return cleaned

    @property
    def llm_enabled(self) -> bool:
        return bool(
            self.openai_api_key
            and self.openai_api_key.get_secret_value().strip()
        )

    @property
    def discord_notifications_configured(self) -> bool:
        token = self.discord_bot_token
        if token is None:
            return False
        token_value = (
            token.get_secret_value()
            if hasattr(token, "get_secret_value")
            else str(token)
        )
        return bool(
            token_value.strip()
            and any(
                (
                    self.discord_daily_briefings_channel_id,
                    self.discord_reconcile_alerts_channel_id,
                    self.discord_ai_workspace_channel_id,
                )
            )
        )

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("must be a valid IANA timezone") from exc
        return value

    @field_validator("week_start_day")
    @classmethod
    def _valid_week_start(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _WEEKDAYS:
            raise ValueError("must be a weekday name")
        return normalized

    @field_validator("daily_task_limit")
    @classmethod
    def _fixed_daily_limit(cls, value: int) -> int:
        if value != 3:
            raise ValueError("must be 3; the daily ceiling is a product invariant")
        return value

    @field_validator("morning_prompt_time", "evening_prompt_time")
    @classmethod
    def _valid_clock_time(cls, value: str) -> str:
        _parse_hhmm(value)
        return value

    @field_validator("weekly_availability_json")
    @classmethod
    def _valid_availability(cls, value: str) -> str:
        try:
            parsed: Any = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("must be a JSON object keyed by weekday")
        for day, windows in parsed.items():
            if not isinstance(day, str) or day.lower() not in _WEEKDAYS:
                raise ValueError("unknown weekday in availability")
            if not isinstance(windows, list):
                raise ValueError("each weekday must map to a list of windows")
            parsed_windows: list[tuple[time, time]] = []
            for window in windows:
                if not isinstance(window, dict) or set(window) != {"start", "end"}:
                    raise ValueError("each window needs exactly start and end")
                start = _parse_hhmm(str(window["start"]))
                end = _parse_hhmm(str(window["end"]))
                if end <= start:
                    raise ValueError("availability end must be after start")
                parsed_windows.append((start, end))
            parsed_windows.sort()
            for previous, current in zip(
                parsed_windows, parsed_windows[1:], strict=False
            ):
                if current[0] < previous[1]:
                    raise ValueError("availability windows must not overlap")
        return value

    @property
    def resolved_ws_url(self) -> str:
        """Return the agent WebSocket URL, deriving it when not overridden."""
        if self.switch_ws_url:
            return self.switch_ws_url
        parsed = urlparse(self.switch_base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = f"/agents/{self.switch_agent_id}/connection/ws"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))

    def safe_summary(self) -> dict[str, object]:
        """Operational summary with no secrets and no private participant IDs."""
        return {
            "app_env": self.app_env,
            "switch_base_url": self.switch_base_url,
            "health_bind": f"{self.health_bind_host}:{self.health_bind_port}",
            "database": self.database_url,
            "timezone": self.timezone,
            "capacity_pct": self.capacity_pct,
            "week_start_day": self.week_start_day,
            "max_message_chars": self.max_message_chars,
            "llm_model": self.openai_model,
            "llm_enabled": self.llm_enabled,
            "discord_notifications_configured": (
                self.discord_notifications_configured
            ),
        }


def load_settings(env_file: str | None = None) -> Settings:
    """Load settings from an explicit file, ``ZASKY_ENV_FILE``, or ``.env``.

    An explicitly supplied path must exist. If no file is supplied or found,
    settings come from the process environment only, and missing required
    values fail validation.
    """
    explicit = env_file or os.getenv("ZASKY_ENV_FILE")
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return Settings(_env_file=str(path))  # type: ignore[call-arg]

    default = Path(".env")
    if default.is_file():
        return Settings(_env_file=str(default))  # type: ignore[call-arg]
    return Settings()  # type: ignore[call-arg]
