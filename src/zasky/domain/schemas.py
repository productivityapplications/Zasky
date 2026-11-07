"""Strict request schemas for the seven domain tools.

These schemas are the model-facing surface. Trusted application code injects
owner/room/current-time/proposal context; the model cannot supply them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EntryType = Literal["year_goal", "month_commitment", "fixed_event"]
Operation = Literal["create", "update"]
Priority = Literal["high", "normal", "low"]
Battery = Literal["low", "medium", "high"]
TaskAction = Literal["park", "resume"]
QueryState = Literal[
    "today",
    "week",
    "month",
    "goals",
    "deadlines",
    "task",
    "commitment",
    "status",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddCommitmentRequest(StrictModel):
    operation: Operation
    entry_type: EntryType
    title: str = Field(min_length=1, max_length=200)
    entity_id: str | None = None
    year: int | None = Field(default=None, ge=2000, le=2200)
    month: int | None = Field(default=None, ge=1, le=12)
    goal_id: str | None = None
    evidence_of_done: str | None = Field(default=None, max_length=1000)
    est_min: int | None = Field(default=None, gt=0)
    deadline_local_date: date | None = None
    consequence: str | None = Field(default=None, max_length=1000)
    priority: Priority = "normal"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None

    @model_validator(mode="after")
    def validate_entry(self) -> AddCommitmentRequest:
        if self.operation == "update" and not self.entity_id:
            raise ValueError("entity_id is required for update")
        if self.entry_type == "year_goal":
            if self.operation == "create" and (self.year is None or not self.evidence_of_done):
                raise ValueError("year_goal create requires year and evidence_of_done")
        elif self.entry_type == "month_commitment":
            if self.operation == "create" and (
                self.year is None or self.month is None or self.est_min is None
            ):
                raise ValueError("month_commitment create requires year, month, est_min")
        elif self.entry_type == "fixed_event":
            if self.operation == "create" and (self.starts_at is None or self.ends_at is None):
                raise ValueError("fixed_event create requires starts_at and ends_at")
            if self.starts_at is not None and self.ends_at is not None:
                if self.ends_at <= self.starts_at:
                    raise ValueError("ends_at must be after starts_at")
        return self


class PlaceWeekTask(StrictModel):
    commitment_id: str | None = None
    task_title: str = Field(min_length=1, max_length=200)
    est_min: int = Field(gt=0)
    scheduled_date: date | None = None
    ad_hoc: bool = False
    execution_type: Literal["human", "ai"] = "human"


class PlaceWeekRequest(StrictModel):
    week_start: date
    tasks: list[PlaceWeekTask] = Field(min_length=1, max_length=30)


class PlanDayRequest(StrictModel):
    date: date
    battery: Battery


class ReconcileRequest(StrictModel):
    what_happened: str = Field(min_length=1, max_length=2000)
    now_iso: datetime
    from_date: date | None = None
    to_date: date | None = None


class ParkTaskRequest(StrictModel):
    task_id: str
    action: TaskAction
    resume_note: str | None = Field(default=None, max_length=1000)
    actual_min: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_park(self) -> ParkTaskRequest:
        if self.action == "park" and not (self.resume_note or "").strip():
            raise ValueError("park requires a nonempty resume_note")
        return self


class CompleteTaskRequest(StrictModel):
    task_id: str
    actual_min: int | None = Field(default=None, ge=0)


class QueryRequest(StrictModel):
    state: QueryState
    horizon: str | None = None
    entity_id: str | None = None


def add_commitment_schema() -> dict[str, Any]:
    """Expose every field as required so the model supplies conditional data.

    The Pydantic request still validates per entry type. Making the fields
    visible as required prevents the common omission of year/month for a month
    commitment while keeping nulls valid for irrelevant fields.
    """
    schema = AddCommitmentRequest.model_json_schema()
    properties = schema.get("properties", {})
    schema["required"] = sorted(properties.keys())
    return schema


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "add_commitment",
        "description": (
            "Propose creation or update of an owner-authored year goal, month "
            "commitment or fixed event. Returns a record proposal; nothing is "
            "written until exact owner approval."
        ),
        "parameters": add_commitment_schema(),
    },
    {
        "type": "function",
        "name": "place_week",
        "description": (
            "Propose owner-named work items into a week pool. The application "
            "computes capacity, slack and fixed-event conflicts; no task titles "
            "may be invented."
        ),
        "parameters": PlaceWeekRequest.model_json_schema(),
    },
    {
        "type": "function",
        "name": "plan_day",
        "description": (
            "Propose a day plan from active approved week-pool tasks for one "
            "date, including battery shaping and backplan."
        ),
        "parameters": PlanDayRequest.model_json_schema(),
    },
    {
        "type": "function",
        "name": "reconcile",
        "description": (
            "Propose recovery after a disruption from existing week-pool tasks; "
            "preserve fixed events and report week feasibility arithmetic."
        ),
        "parameters": ReconcileRequest.model_json_schema(),
    },
    {
        "type": "function",
        "name": "park_task",
        "description": (
            "Park or resume one task. Parking requires a concrete resume note; "
            "only an explicit owner status request may apply immediately."
        ),
        "parameters": ParkTaskRequest.model_json_schema(),
    },
    {
        "type": "function",
        "name": "complete_task",
        "description": (
            "Mark one owner-selected task complete; idempotent and owner-only."
        ),
        "parameters": CompleteTaskRequest.model_json_schema(),
    },
    {
        "type": "function",
        "name": "query",
        "description": "Read-only bounded query over stored plan state.",
        "parameters": QueryRequest.model_json_schema(),
    },
]


def tool_names() -> list[str]:
    return [tool["name"] for tool in TOOL_DEFINITIONS]
