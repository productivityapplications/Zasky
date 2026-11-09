"""Deterministic Daily Briefing message for the room.

Switch 0.31.0 exposes no scheduled-event or pin operation. The briefing is
posted as a formatted room message and saved as a room document where possible;
pinning remains a manual Discord action.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from zasky.agent.plan_notes import plan_transparency_notes
from zasky.config import Settings
from zasky.integrations.calendar import google_calendar_day_quick_add_url
from zasky.planner.core import as_utc, week_start_for
from zasky.storage.database import Database
from zasky.storage.models import (
    DayPlan,
    DayPlanItem,
    FixedEvent,
    WeekPlacement,
    WeekTask,
)


def _escape_md(text: str) -> str:
    escaped = str(text).replace("\\", "\\\\")
    for char in ("*", "_", "`", "~", "|"):
        escaped = escaped.replace(char, "\\" + char)
    return escaped


def _display_time(value: datetime | None, tz: ZoneInfo) -> str:
    if value is None:
        return "Unavailable"
    return as_utc(value).astimezone(tz).strftime("%I:%M %p")


class BriefingBuilder:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._db = database
        self._settings = settings

    async def build(self, local_date: date) -> str:
        tz = ZoneInfo(self._settings.timezone)
        async with self._db.locked_session() as session:
            plan = await session.scalar(
                select(DayPlan)
                .where(DayPlan.local_date == local_date, DayPlan.status == "approved")
                .order_by(DayPlan.revision.desc())
                .limit(1)
            )
            header = (
                f"📅 **Daily Briefing — "
                f"{local_date.strftime('%A, %b')} {local_date.day}**"
            )
            if plan is None:
                return (
                    f"{header}\n\n"
                    "No approved day plan yet. Ask me to plan the day."
                )
            rows = (
                await session.execute(
                    select(DayPlanItem, WeekTask)
                    .join(WeekTask, DayPlanItem.task_id == WeekTask.id)
                    .where(DayPlanItem.day_plan_id == plan.id)
                    .order_by(DayPlanItem.position)
                )
            ).all()
            week_start = week_start_for(
                local_date, self._settings.week_start_day
            )
            active_week_task_ids = set(
                (
                    await session.execute(
                        select(WeekTask.id)
                        .join(
                            WeekPlacement,
                            WeekTask.placement_id == WeekPlacement.id,
                        )
                        .where(
                            WeekPlacement.week_start == week_start,
                            WeekPlacement.status == "active",
                            WeekTask.status == "active",
                        )
                    )
                )
                .scalars()
                .all()
            )
            selected_task_ids = {task.id for _item, task in rows}
            not_selected_count = len(
                active_week_task_ids - selected_task_ids
            )
            selected_est_min_total = sum(
                item.planned_est_min for item, _task in rows
            )
            events = (
                await session.execute(
                    select(FixedEvent).where(FixedEvent.status == "active")
                )
            ).scalars().all()
            day_start = datetime.combine(local_date, datetime.min.time(), tzinfo=tz)
            day_end = day_start.replace(hour=23, minute=59, second=59)
            fixed = [
                event
                for event in events
                if as_utc(event.starts_at_utc) < day_end.astimezone(UTC)
                and as_utc(event.ends_at_utc) > day_start.astimezone(UTC)
            ]

        must: list[str] = []
        should: list[str] = []
        for item, task in rows:
            line = (
                f"- {'📌' if item.disposition == 'must' else '✅'} "
                f"**{_escape_md(task.title)}** — "
                f"{_display_time(item.planned_start_utc, tz)}–"
                f"{_display_time(item.planned_end_utc, tz)}"
            )
            if item.disposition == "must":
                must.append(line)
            else:
                should.append(line)
        lines = [header, "", "**MUST DO:**"]
        lines.extend(must or ["- None"])
        lines.extend(["", "**SHOULD DO:**"])
        lines.extend(should or ["- None"])
        if fixed:
            lines.extend(["", "**FIXED:**"])
            for event in fixed:
                lines.append(
                    f"- 📍 **{_escape_md(event.title)}** — "
                    f"{_display_time(event.starts_at_utc, tz)}–"
                    f"{_display_time(event.ends_at_utc, tz)}"
                )
        notes = plan_transparency_notes(
            battery=plan.battery,
            must_count=len(must),
            should_count=len(should),
            selected_est_min_total=selected_est_min_total,
            not_selected_count=not_selected_count,
        )
        if notes:
            lines.extend(["", *notes])
        lines.extend(
            [
                "",
                f"⏰ **Latest Wake:** {_display_time(plan.latest_wake_utc, tz)}",
                "*One must. Three max. Slack protected.*",
            ]
        )
        calendar_details = []
        for item, task in rows:
            calendar_details.append(
                f"{item.disposition.upper()}: {task.title} "
                f"({_display_time(item.planned_start_utc, tz)}–"
                f"{_display_time(item.planned_end_utc, tz)})"
            )
        calendar_url = google_calendar_day_quick_add_url(
            title=(
                f"Zasky Plan — {local_date.strftime('%A, %b')} "
                f"{local_date.day}"
            ),
            local_date=local_date,
            details="\n".join(calendar_details),
        )
        lines.extend(
            [
                "",
                "📅 **Add to Google Calendar:** "
                f"[Open in Google Calendar]({calendar_url})",
            ]
        )
        return "\n".join(lines)
