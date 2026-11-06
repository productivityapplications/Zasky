from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from zasky.domain.schemas import (
    AddCommitmentRequest,
    CompleteTaskRequest,
    ParkTaskRequest,
    PlaceWeekTask,
    PlanDayRequest,
    QueryRequest,
    tool_names,
)


def test_exactly_seven_domain_tools() -> None:
    assert set(tool_names()) == {
        "add_commitment",
        "place_week",
        "plan_day",
        "reconcile",
        "park_task",
        "complete_task",
        "query",
    }
    assert len(tool_names()) == 7


def test_unknown_tool_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PlanDayRequest.model_validate(
            {"date": "2026-11-06", "battery": "low", "task_id": "invented"}
        )


def test_update_requires_entity_id() -> None:
    with pytest.raises(ValidationError):
        AddCommitmentRequest(
            operation="update",
            entry_type="year_goal",
            title="A goal",
        )


def test_park_requires_a_resume_note() -> None:
    with pytest.raises(ValidationError):
        ParkTaskRequest(task_id="task-1", action="park", resume_note="   ")


def test_negative_actual_time_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CompleteTaskRequest(task_id="task-1", actual_min=-1)


def test_zero_estimate_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PlaceWeekTask(
            commitment_id="commitment-1",
            task_title="A task",
            est_min=0,
            scheduled_date=date(2026, 11, 6),
        )


def test_invalid_query_state_is_rejected() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(state="everything")  # type: ignore[arg-type]
