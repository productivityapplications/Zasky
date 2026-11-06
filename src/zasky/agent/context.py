"""Minimal, bounded owner-plan context for the model.

No raw room history, secrets, host paths or participant IDs are included. The
prompt marks this payload as untrusted data, never instructions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from zasky.config import Settings
from zasky.planner.core import WEEKDAYS, week_dates, week_start_for
from zasky.storage.database import Database
from zasky.storage.models import (
    DayPlan,
    DayPlanItem,
    FixedEvent,
    MonthCommitment,
    OwnerConfig,
    PendingProposal,
    WeekPlacement,
    WeekTask,
    YearGoal,
)


class ContextBuilder:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._db = database
        self._settings = settings

    async def build(self, recent_messages: list[dict[str, object]] | None = None) -> str:
        now = datetime.now(UTC)
        async with self._db.locked_session() as session:
            config = await session.get(OwnerConfig, 1)
            tz = ZoneInfo(config.timezone if config else self._settings.timezone)
            local_now = now.astimezone(tz)
            today = local_now.date()
            week_start = week_start_for(
                today,
                config.week_start_weekday if config else self._settings.week_start_day,
            )
            goals = (
                await session.execute(
                    select(YearGoal)
                    .where(YearGoal.status == "active")
                    .order_by(YearGoal.year, YearGoal.created_at)
                    .limit(5)
                )
            ).scalars().all()
            commitments = (
                await session.execute(
                    select(MonthCommitment)
                    .where(MonthCommitment.status == "active")
                    .order_by(MonthCommitment.deadline_local_date)
                    .limit(12)
                )
            ).scalars().all()
            week_tasks = (
                await session.execute(
                    select(WeekTask, WeekPlacement)
                    .join(WeekPlacement, WeekTask.placement_id == WeekPlacement.id)
                    .where(
                        WeekPlacement.week_start == week_start,
                        WeekPlacement.status == "active",
                    )
                    .order_by(WeekTask.scheduled_date, WeekTask.created_at)
                    .limit(30)
                )
            ).all()
            day_plan = await session.scalar(
                select(DayPlan)
                .where(DayPlan.local_date == today, DayPlan.status == "approved")
                .order_by(DayPlan.revision.desc())
                .limit(1)
            )
            day_items = []
            if day_plan is not None:
                rows = (
                    await session.execute(
                        select(DayPlanItem).where(
                            DayPlanItem.day_plan_id == day_plan.id
                        )
                    )
                ).scalars().all()
                for item in rows:
                    task = await session.get(WeekTask, item.task_id)
                    if task is not None:
                        day_items.append(
                            {
                                "task_id": task.id,
                                "title": task.title,
                                "disposition": item.disposition,
                                "est_min": item.planned_est_min,
                                "start_utc": (
                                    item.planned_start_utc.isoformat()
                                    if item.planned_start_utc
                                    else None
                                ),
                            }
                        )
            fixed_events = (
                await session.execute(
                    select(FixedEvent)
                    .where(FixedEvent.status == "active")
                    .order_by(FixedEvent.starts_at_utc)
                    .limit(10)
                )
            ).scalars().all()
            proposals = (
                await session.execute(
                    select(PendingProposal)
                    .where(PendingProposal.status == "pending")
                    .order_by(PendingProposal.created_at.desc())
                    .limit(5)
                )
            ).scalars().all()

            this_week = {
                WEEKDAYS[day.weekday()]: day.isoformat()
                for day in week_dates(week_start)
            }
            next_start = week_start + timedelta(days=7)
            next_week = {
                WEEKDAYS[day.weekday()]: day.isoformat()
                for day in week_dates(next_start)
            }
            payload = {
                "now_local": local_now.isoformat(),
                "timezone": str(tz),
                "week_start": week_start.isoformat(),
                "dates": {
                    "today": today.isoformat(),
                    "tomorrow": (today + timedelta(days=1)).isoformat(),
                    "this_week": this_week,
                    "next_week": next_week,
                },
                "capacity_pct": config.capacity_pct if config else 65,
                "buffers": {
                    "morning_prep_min": config.morning_prep_min if config else 30,
                    "commute_min": config.commute_buffer_min if config else 0,
                    "transition_min": (
                        config.transition_buffer_min if config else 10
                    ),
                },
                "goals": [
                    {
                        "id": goal.id,
                        "year": goal.year,
                        "title": goal.title,
                        "evidence": goal.evidence_of_done,
                        "status": goal.status,
                    }
                    for goal in goals
                ],
                "commitments": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "month": f"{item.year}-{item.month:02d}",
                        "est_total_min": item.est_total_min,
                        "deadline": (
                            item.deadline_local_date.isoformat()
                            if item.deadline_local_date
                            else None
                        ),
                        "consequence": item.consequence,
                        "priority": item.priority,
                        "status": item.status,
                    }
                    for item in commitments
                ],
                "fixed_events": [
                    {
                        "id": event.id,
                        "title": event.title,
                        "starts_at_utc": event.starts_at_utc.isoformat(),
                        "ends_at_utc": event.ends_at_utc.isoformat(),
                    }
                    for event in fixed_events
                ],
                "week_tasks": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "est_min": task.est_min,
                        "scheduled_date": task.scheduled_date.isoformat(),
                        "status": task.status,
                        "ad_hoc": task.ad_hoc,
                    }
                    for task, _placement in week_tasks
                ],
                "today_plan": {
                    "date": today.isoformat(),
                    "battery": day_plan.battery if day_plan else None,
                    "latest_wake_utc": (
                        day_plan.latest_wake_utc.isoformat()
                        if day_plan and day_plan.latest_wake_utc
                        else None
                    ),
                    "items": day_items,
                },
                "pending_proposals": [
                    {
                        "code": proposal.code,
                        "type": proposal.proposal_type,
                        "expires_at": proposal.expires_at.isoformat(),
                    }
                    for proposal in proposals
                ],
                "recent_room_messages": (recent_messages or [])[-10:],
            }
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(text) > 12_000:
            text = text[:12_000] + ',"truncated":true}'
        return text
