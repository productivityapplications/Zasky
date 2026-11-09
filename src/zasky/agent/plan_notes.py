"""Deterministic transparency notes for day-plan templates.

The notes explain why a plan is short. They are generated from tool payload
values only; the model never supplies the counts or wording.
"""

from __future__ import annotations

# A plan at or below this total selected time is treated as a deliberately light
# day for the "protect your energy" note.
LIGHT_PLAN_MINUTES = 90


def plan_transparency_notes(
    *,
    battery: str,
    must_count: int,
    should_count: int,
    selected_est_min_total: int,
    not_selected_count: int,
) -> list[str]:
    """Return Discord-ready notes for unselected work and plan size."""
    notes: list[str] = []

    if not_selected_count > 0:
        noun = "task" if not_selected_count == 1 else "tasks"
        if battery == "low":
            cap_text = (
                "I cap plans at 3 tasks (2 on low battery) to prevent burnout"
            )
        else:
            cap_text = "I cap plans at 3 tasks to prevent burnout"
        notes.append(
            f"*Note: You have {not_selected_count} other active {noun} in your "
            f"week pool. Because your battery is {battery} and {cap_text}, "
            "I've left them in the queue for another day.*"
        )

    if selected_est_min_total <= LIGHT_PLAN_MINUTES:
        notes.append(
            "*I kept your plan light today to protect your energy.*"
        )

    if battery == "low":
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
