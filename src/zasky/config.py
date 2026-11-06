"""Validated runtime configuration.

Secrets are represented as :class:`~pydantic.SecretStr` so accidental repr or
logging cannot expose them. Validation errors are reported by field name only
in the CLI, never by value.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    def _sqlite_only(cls, value: str) -> str:
        if not value.startswith("sqlite+aiosqlite:///"):
            raise ValueError("must start with sqlite+aiosqlite:///")
        return value

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
            "max_message_chars": self.max_message_chars,
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
