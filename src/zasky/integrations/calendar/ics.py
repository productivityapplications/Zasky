"""Dynamic iCalendar feed for fixed events and approved day-plan tasks."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select

from zasky.config import Settings
from zasky.planner.core import as_utc
from zasky.storage.database import Database
from zasky.storage.models import (
    DayPlan,
    DayPlanItem,
    FixedEvent,
    MonthCommitment,
    WeekPlacement,
    WeekTask,
)


def _fmt_utc(value: datetime) -> str:
    return as_utc(value).strftime("%Y%m%dT%H%M%SZ")


def _escape(value: str) -> str:
    cleaned = str(value).replace("\\", "\\\\")
    cleaned = cleaned.replace(";", "\\;").replace(",", "\\,")
    return cleaned.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _fold(line: str, limit: int = 74) -> str:
    if len(line) <= limit:
        return line
    chunks: list[str] = []
    remaining = line
    while len(remaining) > limit:
        chunks.append(remaining[:limit])
        remaining = " " + remaining[limit:]
    chunks.append(remaining)
    return "\r\n".join(chunks)


def _calendar_lines(
    *,
    settings: Settings,
    stamp: str,
    events: Iterable[tuple[datetime, list[str]]],
) -> str:
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Zasky//Planning Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Zasky",
        f"X-WR-TIMEZONE:{settings.timezone}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    body: list[str] = []
    for _start, lines in sorted(events, key=lambda item: item[0]):
        body.extend(lines)
    lines = header + body + ["END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


async def build_calendar_feed(
    database: Database,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> str:
    """Build the current calendar feed from Postgres.

    Fixed events are active owner events. Tasks are only from approved day
    plans with explicit planned times. Every task event gets a display alarm.
    """
    current = as_utc(now or datetime.now(UTC))
    stamp = _fmt_utc(current)
    alarm = settings.calendar_alarm_minutes
    async with database.locked_session() as session:
        fixed = (
            await session.execute(
                select(FixedEvent)
                .where(FixedEvent.status == "active")
                .order_by(FixedEvent.starts_at_utc)
            )
        ).scalars().all()
        task_rows = (
            await session.execute(
                select(
                    DayPlanItem,
                    WeekTask,
                    DayPlan,
                    MonthCommitment,
                )
                .join(DayPlan, DayPlanItem.day_plan_id == DayPlan.id)
                .join(WeekTask, DayPlanItem.task_id == WeekTask.id)
                .join(WeekPlacement, WeekTask.placement_id == WeekPlacement.id)
                .outerjoin(
                    MonthCommitment,
                    WeekPlacement.commitment_id == MonthCommitment.id,
                )
                .where(
                    DayPlan.status == "approved",
                    DayPlanItem.planned_start_utc.is_not(None),
                    DayPlanItem.planned_end_utc.is_not(None),
                )
                .order_by(DayPlanItem.planned_start_utc)
            )
        ).all()

    events: list[tuple[datetime, list[str]]] = []
    for event in fixed:
        start = as_utc(event.starts_at_utc)
        end = as_utc(event.ends_at_utc)
        events.append(
            (
                start,
                [
                    "BEGIN:VEVENT",
                    f"UID:zasky-fixed-{event.id}@zasky",
                    f"DTSTAMP:{stamp}",
                    f"DTSTART:{_fmt_utc(start)}",
                    f"DTEND:{_fmt_utc(end)}",
                    f"SUMMARY:{_escape(event.title)}",
                    "DESCRIPTION:Fixed event in Zasky",
                    "CATEGORIES:Zasky,Fixed Event",
                    "STATUS:CONFIRMED",
                    "END:VEVENT",
                ],
            )
        )

    for item, task, plan, commitment in task_rows:
        if item.planned_start_utc is None or item.planned_end_utc is None:
            continue
        start = as_utc(item.planned_start_utc)
        end = as_utc(item.planned_end_utc)
        description: list[str] = [
            f"Disposition: {item.disposition.upper()}",
            f"Estimate: {item.planned_est_min} minutes",
        ]
        if commitment is not None:
            description.append(f"Commitment: {commitment.title}")
        description.append(f"Plan date: {plan.local_date.isoformat()}")
        events.append(
            (
                start,
                [
                    "BEGIN:VEVENT",
                    f"UID:zasky-task-{item.id}@zasky",
                    f"DTSTAMP:{stamp}",
                    f"DTSTART:{_fmt_utc(start)}",
                    f"DTEND:{_fmt_utc(end)}",
                    f"SUMMARY:{_escape(task.title)}",
                    f"DESCRIPTION:{_escape(chr(10).join(description))}",
                    "CATEGORIES:Zasky,Task",
                    "STATUS:CONFIRMED",
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_escape('Zasky: ' + task.title)}",
                    f"TRIGGER:-PT{alarm}M",
                    "END:VALARM",
                    "END:VEVENT",
                ],
            )
        )

    return _calendar_lines(settings=settings, stamp=stamp, events=events)


__all__ = ["build_calendar_feed"]
