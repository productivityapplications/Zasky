"""Deterministic transparency notes for day-plan templates.

The notes explain why a plan is short or overloaded. They are generated from
tool payload values only; the model never supplies the counts or wording.
"""

from __future__ import annotations

# A plan at or below this total selected time is treated as a deliberately light
# day for the "protect your energy" note.
LIGHT_PLAN_MINUTES = 90


def _hours(minutes: int) -> str:
    """Format minutes as a compact hour label for Discord."""
    whole, remainder = divmod(max(0, minutes), 60)
    if remainder == 0:
        return f"{whole} hour" if whole == 1 else f"{whole} hours"
    return f"{whole}h {remainder}m" if whole else f"{remainder}m"


def plan_transparency_notes(
    *,
    battery: str,
    must_count: int,
    should_count: int,
    selected_count: int,
    selected_est_min_total: int,
    not_selected_count: int,
    week_pool_not_selected_count: int = 0,
    override_limits: bool = False,
    daily_available_min: int | None = None,
    unplaced_count: int = 0,
) -> list[str]:
    """Return Discord-ready notes for unselected work, overrides and plan size."""
    notes: list[str] = []

    if override_limits:
        if unplaced_count > 0:
            noun = "task" if unplaced_count == 1 else "tasks"
            notes.append(
                f"*⚠️ Override active: {unplaced_count} {noun} could not fit "
                "before midnight and remain in the queue.*"
            )
        if (
            daily_available_min is not None
            and selected_est_min_total > daily_available_min
            and unplaced_count == 0
        ):
            notes.append(
                "*⚠️ Override active: You have "
                f"{_hours(selected_est_min_total)} of tasks and "
                f"{_hours(daily_available_min)} available. I scheduled them "
                "all, but you may not finish.*"
            )
    elif not_selected_count > 0:
        more_noun = "task" if not_selected_count == 1 else "tasks"
        if selected_count == 1:
            scheduled_text = "I've scheduled your top task."
        else:
            scheduled_text = f"I've scheduled your top {selected_count} tasks."
        notes.append(
            f"*{scheduled_text} "
            f"You have {not_selected_count} more {more_noun} in the queue. "
            'Reply "override limits" if you want me to schedule all of them.*'
        )
    elif week_pool_not_selected_count > 0:
        noun = "task" if week_pool_not_selected_count == 1 else "tasks"
        notes.append(
            f"*You have {week_pool_not_selected_count} other active {noun} "
            "elsewhere in your week pool.*"
        )

    if selected_est_min_total <= LIGHT_PLAN_MINUTES:
        notes.append(
            "*I kept your plan light today to protect your energy.*"
        )

    if battery == "low" and not override_limits:
        if must_count == 1 and should_count == 1:
            notes.append(
                "*Since your battery is low, I selected only one MUST and one "
                "short SHOULD task.*"
            )
        elif must_count == 1 and should_count == 0:
            notes.append(
                "*Since your battery is low, I selected only one MUST task.*"
            )
        elif must_count == 0 and should_count == 1:
            notes.append(
                "*Since your battery is low, I selected only one short SHOULD "
                "task.*"
            )
        else:
            notes.append(
                f"*Since your battery is low, I selected {must_count} MUST and "
                f"{should_count} SHOULD tasks.*"
            )

    return notes
