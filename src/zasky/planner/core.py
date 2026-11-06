"""Deterministic capacity, scheduling, backplan and feasibility arithmetic.

All authoritative time/capacity values come from this module. The model may
explain them but never computes them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from zasky.storage.models import FixedEvent, OwnerConfig

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))


@dataclass(frozen=True)
class Capacity:
    available_min: int
    budget_min: int
    slack_min: int


@dataclass(frozen=True)
class ScheduledItem:
    task_id: str
    start_utc: datetime
    end_utc: datetime
    est_min: int


@dataclass(frozen=True)
class ScheduleResult:
    scheduled: list[ScheduledItem]
    unplaced: list[str]


def zone(config: OwnerConfig) -> ZoneInfo:
    return ZoneInfo(config.timezone)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def week_start_for(local_date: date, weekday_name: str) -> date:
    target = WEEKDAYS.index(weekday_name)
    delta = (local_date.weekday() - target) % 7
    return local_date - timedelta(days=delta)


def week_dates(week_start: date) -> list[date]:
    return [week_start + timedelta(days=offset) for offset in range(7)]


def month_dates(year: int, month: int) -> list[date]:
    first = date(year, month, 1)
    if month == 12:
        after = date(year + 1, 1, 1)
    else:
        after = date(year, month + 1, 1)
    return [first + timedelta(days=offset) for offset in range((after - first).days)]


def parse_availability(config: OwnerConfig) -> dict[str, list[tuple[time, time]]]:
    raw = json.loads(config.availability_json or "{}")
    parsed: dict[str, list[tuple[time, time]]] = {}
    for day, windows in raw.items():
        parsed[day.lower()] = [
            (time.fromisoformat(window["start"]), time.fromisoformat(window["end"]))
            for window in windows
        ]
    return parsed


def _local_bounds(local_date: date, window: tuple[time, time], tz: ZoneInfo) -> Interval:
    return Interval(
        datetime.combine(local_date, window[0], tzinfo=tz),
        datetime.combine(local_date, window[1], tzinfo=tz),
    )


def _fixed_local(event: FixedEvent, tz: ZoneInfo) -> Interval:
    return Interval(
        as_utc(event.starts_at_utc).astimezone(tz),
        as_utc(event.ends_at_utc).astimezone(tz),
    )


def _overlap_minutes(left: Interval, right: Interval) -> int:
    start = max(left.start, right.start)
    end = min(left.end, right.end)
    if end <= start:
        return 0
    return int((end - start).total_seconds() // 60)


def _subtract(base: Interval, cuts: list[Interval]) -> list[Interval]:
    remaining = [base]
    for cut in cuts:
        next_remaining: list[Interval] = []
        for interval in remaining:
            if cut.end <= interval.start or cut.start >= interval.end:
                next_remaining.append(interval)
                continue
            if cut.start > interval.start:
                next_remaining.append(Interval(interval.start, min(cut.start, interval.end)))
            if cut.end < interval.end:
                next_remaining.append(Interval(max(cut.end, interval.start), interval.end))
        remaining = next_remaining
    return [interval for interval in remaining if interval.end > interval.start]


def _event_blocks(event: FixedEvent, tz: ZoneInfo, buffer_min: int) -> Interval:
    local = _fixed_local(event, tz)
    return Interval(local.start, local.end + timedelta(minutes=buffer_min))


def daily_capacity(
    local_date: date,
    config: OwnerConfig,
    fixed_events: list[FixedEvent],
) -> Capacity:
    tz = zone(config)
    availability = parse_availability(config)
    windows = availability.get(WEEKDAYS[local_date.weekday()], [])
    available = 0
    for window in windows:
        bounds = _local_bounds(local_date, window, tz)
        overlap = 0
        buffers = 0
        for event in fixed_events:
            event_interval = _fixed_local(event, tz)
            if event_interval.start.date() != local_date:
                continue
            event_overlap = _overlap_minutes(bounds, event_interval)
            if event_overlap > 0:
                overlap += event_overlap
                buffers += min(config.transition_buffer_min, bounds.minutes)
        available += max(0, bounds.minutes - overlap - min(buffers, bounds.minutes))
    budget = math.floor(available * config.capacity_pct / 100)
    return Capacity(available_min=available, budget_min=budget, slack_min=available - budget)


def week_capacity(
    week_start: date,
    config: OwnerConfig,
    fixed_events: list[FixedEvent],
) -> Capacity:
    available = sum(
        daily_capacity(day, config, fixed_events).available_min
        for day in week_dates(week_start)
    )
    budget = math.floor(available * config.capacity_pct / 100)
    return Capacity(available_min=available, budget_min=budget, slack_min=available - budget)


def month_capacity(
    year: int,
    month: int,
    config: OwnerConfig,
    fixed_events: list[FixedEvent],
) -> Capacity:
    available = sum(
        daily_capacity(day, config, fixed_events).available_min
        for day in month_dates(year, month)
    )
    budget = math.floor(available * config.capacity_pct / 100)
    return Capacity(available_min=available, budget_min=budget, slack_min=available - budget)


def free_intervals(
    local_date: date,
    config: OwnerConfig,
    fixed_events: list[FixedEvent],
    *,
    not_before: datetime | None = None,
) -> list[Interval]:
    tz = zone(config)
    availability = parse_availability(config)
    windows = availability.get(WEEKDAYS[local_date.weekday()], [])
    cuts = [
        _event_blocks(event, tz, config.transition_buffer_min)
        for event in fixed_events
        if _fixed_local(event, tz).start.date() == local_date
    ]
    intervals: list[Interval] = []
    for window in windows:
        bounds = _local_bounds(local_date, window, tz)
        for interval in _subtract(bounds, cuts):
            if not_before is not None:
                cutoff = not_before.astimezone(tz)
                if interval.end <= cutoff:
                    continue
                if interval.start < cutoff:
                    interval = Interval(cutoff, interval.end)
            intervals.append(interval)
    return sorted(intervals, key=lambda interval: interval.start)


def remaining_week_capacity(
    now_utc: datetime,
    week_start: date,
    config: OwnerConfig,
    fixed_events: list[FixedEvent],
) -> Capacity:
    tz = zone(config)
    now_local = as_utc(now_utc).astimezone(tz)
    available = 0
    for day in week_dates(week_start):
        if day < now_local.date():
            continue
        if day > now_local.date():
            available += daily_capacity(day, config, fixed_events).available_min
            continue
        # Today: only the remaining part of each availability window counts.
        # Recompute the remaining availability explicitly from free intervals.
        available += sum(
            interval.minutes
            for interval in free_intervals(day, config, fixed_events, not_before=now_utc)
        )
    budget = math.floor(available * config.capacity_pct / 100)
    return Capacity(available_min=available, budget_min=budget, slack_min=available - budget)


def schedule_tasks(
    local_date: date,
    tasks: list[tuple[str, int]],
    config: OwnerConfig,
    fixed_events: list[FixedEvent],
    *,
    not_before: datetime | None = None,
) -> ScheduleResult:
    """Greedy whole-task placement; tasks are never split or compressed."""
    intervals = free_intervals(
        local_date, config, fixed_events, not_before=not_before
    )
    scheduled: list[ScheduledItem] = []
    unplaced: list[str] = []
    for task_id, estimate in tasks:
        duration = timedelta(minutes=estimate)
        placed = False
        for index, interval in enumerate(intervals):
            if interval.end - interval.start >= duration:
                start = interval.start
                end = start + duration
                scheduled.append(
                    ScheduledItem(
                        task_id=task_id,
                        start_utc=start.astimezone(UTC),
                        end_utc=end.astimezone(UTC),
                        est_min=estimate,
                    )
                )
                remainder = Interval(end, interval.end)
                if remainder.minutes > 0:
                    intervals[index] = remainder
                else:
                    intervals.pop(index)
                placed = True
                break
        if not placed:
            unplaced.append(task_id)
    return ScheduleResult(scheduled=scheduled, unplaced=unplaced)


@dataclass(frozen=True)
class Backplan:
    first_required_start_utc: datetime
    latest_wake_utc: datetime
    morning_prep_min: int
    commute_buffer_min: int


def backplan(first_required_start: datetime, config: OwnerConfig) -> Backplan:
    start = as_utc(first_required_start)
    latest_wake = start - timedelta(
        minutes=config.morning_prep_min + config.commute_buffer_min
    )
    return Backplan(
        first_required_start_utc=start,
        latest_wake_utc=latest_wake,
        morning_prep_min=config.morning_prep_min,
        commute_buffer_min=config.commute_buffer_min,
    )


@dataclass(frozen=True)
class Feasibility:
    status: str
    remaining_work_min: int
    remaining_budget_min: int
    overage_min: int
    arithmetic: str


def week_feasibility(
    remaining_work_min: int,
    remaining_budget: Capacity,
    *,
    data_complete: bool = True,
) -> Feasibility:
    if not data_complete:
        return Feasibility(
            status="insufficient_data",
            remaining_work_min=remaining_work_min,
            remaining_budget_min=remaining_budget.budget_min,
            overage_min=0,
            arithmetic="availability or fixed-event data is incomplete",
        )
    overage = max(0, remaining_work_min - remaining_budget.budget_min)
    status = "week_holds" if overage == 0 else "week_at_risk"
    return Feasibility(
        status=status,
        remaining_work_min=remaining_work_min,
        remaining_budget_min=remaining_budget.budget_min,
        overage_min=overage,
        arithmetic=(
            f"remaining work {remaining_work_min} min vs budget "
            f"{remaining_budget.budget_min} min; overage {overage} min"
        ),
    )


def deadline_days_left(deadline: date | None, today: date) -> int | None:
    if deadline is None:
        return None
    return (deadline - today).days
