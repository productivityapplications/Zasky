"""Structured JSON logging with conservative redaction.

We never intentionally log message bodies, task text, credentials or headers.
The redactor is a last line of defence for exception text.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b\s*[=:]\s*([^\s,;]+)"
)
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")
_ZASKY_HEADER_RE = re.compile(r"(?i)(x-switch-connection-id\s*[=:]\s*)[^\s,;]+")

_EXTRA_FIELDS = (
    "component",
    "correlation_id",
    "event_sequence",
    "outcome",
    "duration_ms",
    "error_code",
    "connection_status",
)


def redact(value: str) -> str:
    """Redact common credential shapes from a string."""
    value = _BEARER_RE.sub(r"\1<redacted>", value)
    value = _SECRET_ASSIGNMENT_RE.sub(r"\1=<redacted>", value)
    value = _OPENAI_KEY_RE.sub("sk-<redacted>", value)
    value = _ZASKY_HEADER_RE.sub(r"\1<redacted>", value)
    return value


class JsonFormatter(logging.Formatter):
    """One JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger and quiet noisy clients."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("httpx", "httpcore", "websockets", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
