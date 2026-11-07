"""Google Calendar quick-add links for Zasky tasks and day plans."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

GOOGLE_CALENDAR_RENDER = "https://calendar.google.com/calendar/render"


def _fmt_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _clip(value: str, limit: int) -> str:
    cleaned = value.strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


def google_calendar_quick_add_url(
    *,
    title: str,
    start: datetime,
    end: datetime,
    details: str = "",
    location: str = "Zasky",
) -> str:
    """Build a Google Calendar event-template URL for a timed task."""
    params = {
        "action": "TEMPLATE",
        "text": _clip(title, 200),
        "dates": f"{_fmt_utc(start)}/{_fmt_utc(end)}",
        "details": _clip(details, 1800),
        "location": _clip(location, 200),
    }
    return f"{GOOGLE_CALENDAR_RENDER}?{urlencode(params)}"


def google_calendar_day_quick_add_url(
    *,
    title: str,
    local_date: date,
    details: str = "",
    location: str = "Zasky",
) -> str:
    """Build an all-day Google Calendar URL for a Zasky day plan."""
    params = {
        "action": "TEMPLATE",
        "text": _clip(title, 200),
        "dates": (
            f"{local_date.strftime('%Y%m%d')}/"
            f"{(local_date + timedelta(days=1)).strftime('%Y%m%d')}"
        ),
        "details": _clip(details, 1800),
        "location": _clip(location, 200),
    }
    return f"{GOOGLE_CALENDAR_RENDER}?{urlencode(params)}"
