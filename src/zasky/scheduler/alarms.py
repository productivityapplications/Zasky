"""Proactive task-start alarms from approved day plans.

One in-process loop, one active writer, database uniqueness for dedupe. Alarms
are posted through the Switch room operation, never a direct Discord API.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from zasky.config import Settings
from zasky.storage.database import Database
from zasky.storage.models import AlarmDispatch, DayPlan, DayPlanItem, WeekTask
from zasky.switch.operations import SwitchOperations, SwitchOperationsError

logger = logging.getLogger(__name__)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _escape_md(text: str) -> str:
    escaped = str(text).replace("\\", "\\\\")
    for char in ("*", "_", "`", "~", "|"):
        escaped = escaped.replace(char, "\\" + char)
    return escaped


class AlarmScheduler:
    def __init__(
        self,
        database: Database,
        operations: SwitchOperations,
        settings: Settings,
        *,
        interval_seconds: float = 20.0,
        grace_minutes: int = 5,
    ) -> None:
        self._db = database
        self._ops = operations
        self._settings = settings
        self._interval = interval_seconds
        self._grace = timedelta(minutes=grace_minutes)
        self._stop = asyncio.Event()

    async def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "Alarm scheduler tick failed",
                    extra={"component": "scheduler", "error_code": type(exc).__name__},
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except TimeoutError:
                continue

    async def tick(self, *, now: datetime | None = None) -> int:
        current = _aware(now or datetime.now(UTC))
        local_date = current.astimezone(ZoneInfo(self._settings.timezone)).date()
        candidates = await self._candidates(local_date, current)
        sent = 0
        for item_id, task_id, start_utc, task_title, duration in candidates:
            if not (current - self._grace <= start_utc <= current):
                continue
            claimed = await self._claim(item_id, task_id, start_utc)
            if not claimed:
                continue
            message = self._format_message(start_utc, task_title, duration)
            try:
                await self._ops.post_message(message)
            except SwitchOperationsError:
                await self._finish(item_id, start_utc, "failed")
                logger.error(
                    "Alarm post failed",
                    extra={
                        "component": "scheduler",
                        "error_code": "ALARM_POST_FAILED",
                    },
                )
                continue
            await self._finish(item_id, start_utc, "sent")
            sent += 1
            logger.info(
                "Task-start alarm sent",
                extra={"component": "scheduler", "outcome": "sent"},
            )
        return sent

    async def _candidates(
        self, local_date: date, now: datetime
    ) -> list[tuple[str, str, datetime, str, int]]:
        async with self._db.locked_session() as session:
            rows = (
                await session.execute(
                    select(DayPlanItem, WeekTask)
                    .join(DayPlan, DayPlanItem.day_plan_id == DayPlan.id)
                    .join(WeekTask, DayPlanItem.task_id == WeekTask.id)
                    .where(
                        DayPlan.local_date == local_date,
                        DayPlan.status == "approved",
                        WeekTask.status == "active",
                        or_(DayPlanItem.outcome.is_(None), DayPlanItem.outcome == "pending"),
                        DayPlanItem.planned_start_utc.is_not(None),
                    )
                )
            ).all()
            result: list[tuple[str, str, datetime, str, int]] = []
            for item, task in rows:
                if item.planned_start_utc is None:
                    continue
                start = _aware(item.planned_start_utc)
                if start <= now:
                    result.append(
                        (item.id, task.id, start, task.title, item.planned_est_min)
                    )
            return result

    async def _claim(self, item_id: str, task_id: str, start_utc: datetime) -> bool:
        async with self._db.locked_session() as session:
            existing = await session.scalar(
                select(AlarmDispatch.id).where(
                    AlarmDispatch.day_plan_item_id == item_id,
                    AlarmDispatch.scheduled_start_utc == start_utc,
                )
            )
            if existing is not None:
                return False
            session.add(
                AlarmDispatch(
                    id=str(uuid4()),
                    day_plan_item_id=item_id,
                    task_id=task_id,
                    scheduled_start_utc=start_utc,
                    status="pending",
                )
            )
            await session.commit()
            return True

    async def _finish(self, item_id: str, start_utc: datetime, status: str) -> None:
        async with self._db.locked_session() as session:
            row = await session.scalar(
                select(AlarmDispatch).where(
                    AlarmDispatch.day_plan_item_id == item_id,
                    AlarmDispatch.scheduled_start_utc == start_utc,
                )
            )
            if row is not None:
                row.status = status
                row.sent_at = datetime.now(UTC) if status == "sent" else None
                await session.commit()

    def _format_message(
        self, start_utc: datetime, task_title: str, duration: int
    ) -> str:
        local = start_utc.astimezone(ZoneInfo(self._settings.timezone))
        display = local.strftime("%I:%M %p")
        return (
            f"⏰ **Timebox Started:** It's {display}. You planned {duration} min "
            f"for **{_escape_md(task_title)}**. Reply with 'done' or 'park' when "
            "finished."
        )


async def run_once(
    database: Database,
    operations: SwitchOperations,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    """Convenience for tests/maintenance without starting the loop."""
    scheduler = AlarmScheduler(database, operations, settings)
    return await scheduler.tick(now=now)

