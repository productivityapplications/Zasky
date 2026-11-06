"""SQLAlchemy models for Zasky's durable state.

Phase 2 defines the complete MVP schema. Domain services in Phase 3 enforce
the invariants that SQLite cannot express directly; the constraints here are
the last line of defence.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class OwnerConfig(Base):
    __tablename__ = "owner_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_owner_config_singleton"),
        CheckConstraint("capacity_pct BETWEEN 60 AND 70", name="ck_owner_capacity"),
        CheckConstraint("daily_task_limit = 3", name="ck_owner_daily_limit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    owner_switch_participant_id: Mapped[str] = mapped_column(
        String(240), unique=True, nullable=False
    )
    allowed_room_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=65)
    week_start_weekday: Mapped[str] = mapped_column(String(9), nullable=False, default="monday")
    daily_task_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    transition_buffer_min: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    morning_prep_min: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    commute_buffer_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    availability_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    morning_prompt_time: Mapped[str | None] = mapped_column(String(5))
    evening_prompt_time: Mapped[str | None] = mapped_column(String(5))
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timebox_checkins_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class YearGoal(Base):
    __tablename__ = "year_goals"
    __table_args__ = (
        UniqueConstraint("year", "normalized_title", name="uq_year_goals_year_title"),
        CheckConstraint("year BETWEEN 2000 AND 2200", name="ck_year_goals_year"),
        CheckConstraint("length(title) BETWEEN 1 AND 160", name="ck_year_goals_title"),
        CheckConstraint(
            "length(evidence_of_done) BETWEEN 1 AND 1000",
            name="ck_year_goals_evidence",
        ),
        CheckConstraint(
            "status IN ('active','achieved','retired')", name="ck_year_goals_status"
        ),
        Index("ix_year_goals_year_status", "year", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_of_done: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonthCommitment(Base):
    __tablename__ = "month_commitments"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_month_commitments_month"),
        CheckConstraint("est_total_min > 0", name="ck_month_commitments_estimate"),
        CheckConstraint(
            "priority IN ('high','normal','low')", name="ck_month_commitments_priority"
        ),
        CheckConstraint(
            "status IN ('active','completed','renegotiated','cancelled')",
            name="ck_month_commitments_status",
        ),
        CheckConstraint(
            "length(title) BETWEEN 1 AND 200", name="ck_month_commitments_title"
        ),
        Index("ix_month_commitments_year_month_status", "year", "month", "status"),
        Index("ix_month_commitments_deadline", "deadline_local_date"),
        Index("ix_month_commitments_goal", "goal_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("year_goals.id", ondelete="RESTRICT")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    est_total_min: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_local_date: Mapped[date | None] = mapped_column(Date)
    consequence: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(6), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FixedEvent(Base):
    __tablename__ = "fixed_events"
    __table_args__ = (
        CheckConstraint("ends_at_utc > starts_at_utc", name="ck_fixed_events_order"),
        CheckConstraint(
            "status IN ('active','cancelled')", name="ck_fixed_events_status"
        ),
        CheckConstraint("source = 'owner'", name="ck_fixed_events_source"),
        CheckConstraint("length(title) BETWEEN 1 AND 160", name="ck_fixed_events_title"),
        Index("ix_fixed_events_window", "starts_at_utc", "ends_at_utc", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    starts_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WeekPlacement(Base):
    __tablename__ = "week_placements"
    __table_args__ = (
        CheckConstraint(
            "(source_type = 'commitment' AND commitment_id IS NOT NULL) OR "
            "(source_type = 'ad_hoc' AND commitment_id IS NULL)",
            name="ck_week_placements_source",
        ),
        CheckConstraint(
            "status IN ('active','completed','cancelled')",
            name="ck_week_placements_status",
        ),
        CheckConstraint("revision >= 1", name="ck_week_placements_revision"),
        Index("ix_week_placements_week_status", "week_start", "status"),
        Index("ix_week_placements_commitment", "commitment_id"),
        Index(
            "uq_week_placements_commitment_week",
            "commitment_id",
            "week_start",
            unique=True,
            sqlite_where=text("commitment_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    commitment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("month_commitments.id", ondelete="RESTRICT")
    )
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WeekTask(Base):
    __tablename__ = "week_tasks"
    __table_args__ = (
        CheckConstraint("est_min > 0", name="ck_week_tasks_estimate"),
        CheckConstraint("actual_min IS NULL OR actual_min >= 0", name="ck_week_tasks_actual"),
        CheckConstraint(
            "status IN ('active','parked','completed','cancelled')",
            name="ck_week_tasks_status",
        ),
        CheckConstraint(
            "status != 'parked' OR (resume_note IS NOT NULL AND length(resume_note) > 0)",
            name="ck_week_tasks_parked_note",
        ),
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="ck_week_tasks_title"),
        Index("ix_week_tasks_placement_status", "placement_id", "status"),
        Index("ix_week_tasks_date_status", "scheduled_date", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    placement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("week_placements.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    est_min: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    resume_note: Mapped[str | None] = mapped_column(Text)
    actual_min: Mapped[int | None] = mapped_column(Integer)
    ad_hoc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DayPlan(Base):
    __tablename__ = "day_plans"
    __table_args__ = (
        UniqueConstraint("local_date", "revision", name="uq_day_plans_date_revision"),
        CheckConstraint("revision >= 1", name="ck_day_plans_revision"),
        CheckConstraint("battery IN ('low','medium','high')", name="ck_day_plans_battery"),
        CheckConstraint("status IN ('approved','replaced')", name="ck_day_plans_status"),
        CheckConstraint("source IN ('plan_day','reconcile')", name="ck_day_plans_source"),
        Index("ix_day_plans_date_status", "local_date", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    battery: Mapped[str] = mapped_column(String(6), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="approved")
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    earliest_required_start_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    latest_wake_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compressed_plan_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DayPlanItem(Base):
    __tablename__ = "day_plan_items"
    __table_args__ = (
        UniqueConstraint("day_plan_id", "task_id", name="uq_day_plan_items_task"),
        UniqueConstraint("day_plan_id", "position", name="uq_day_plan_items_position"),
        CheckConstraint("position BETWEEN 1 AND 3", name="ck_day_plan_items_position"),
        CheckConstraint(
            "disposition IN ('must','should')", name="ck_day_plan_items_disposition"
        ),
        CheckConstraint("planned_est_min > 0", name="ck_day_plan_items_estimate"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('pending','completed','parked','moved')",
            name="ck_day_plan_items_outcome",
        ),
        CheckConstraint(
            "planned_end_utc IS NULL OR planned_start_utc IS NULL OR "
            "planned_end_utc > planned_start_utc",
            name="ck_day_plan_items_window",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("day_plans.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("week_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(6), nullable=False)
    planned_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_est_min: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(10))


class PendingProposal(Base):
    __tablename__ = "pending_proposals"
    __table_args__ = (
        CheckConstraint(
            "proposal_type IN ('record','week','day','reconcile')",
            name="ck_pending_proposals_type",
        ),
        CheckConstraint(
            "status IN ('pending','approved','rejected','expired','stale')",
            name="ck_pending_proposals_status",
        ),
        CheckConstraint(
            "payload_schema_version >= 1", name="ck_pending_proposals_schema"
        ),
        CheckConstraint("base_revision >= 1", name="ck_pending_proposals_revision"),
        Index("ix_pending_proposals_status_expiry", "status", "expires_at"),
        Index("ix_pending_proposals_scope_status", "scope_key", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_actor: Mapped[str | None] = mapped_column(String(240))
    resolution_reason: Mapped[str | None] = mapped_column(String(200))


class PlanningScopeRevision(Base):
    __tablename__ = "planning_scope_revisions"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_scope_revision_value"),)

    scope_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReminderDispatch(Base):
    __tablename__ = "reminder_dispatches"
    __table_args__ = (
        UniqueConstraint("local_date", "reminder_type", name="uq_reminder_date_type"),
        CheckConstraint(
            "reminder_type IN ('morning','evening')", name="ck_reminder_type"
        ),
        CheckConstraint(
            "status IN ('pending','sent','skipped','failed')", name="ck_reminder_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('owner','agent','system')", name="ck_audit_actor_type"
        ),
        Index("ix_audit_events_created", "created_at"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(8), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(240))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    summary_redacted: Mapped[str] = mapped_column(String(300), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelUsageRecord(Base):
    __tablename__ = "model_usage_records"
    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_usage_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="ck_usage_output_tokens"),
        CheckConstraint(
            "reserved_cost_microusd >= 0", name="ck_usage_reserved_cost"
        ),
        CheckConstraint(
            "actual_cost_microusd IS NULL OR actual_cost_microusd >= 0",
            name="ck_usage_actual_cost",
        ),
        CheckConstraint(
            "status IN ('succeeded','failed','unknown')", name="ck_usage_status"
        ),
        Index("ix_model_usage_occurred", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(
        String(120), unique=True
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_cost_microusd: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    actual_cost_microusd: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)


class AlarmDispatch(Base):
    __tablename__ = "alarm_dispatches"
    __table_args__ = (
        UniqueConstraint(
            "day_plan_item_id",
            "scheduled_start_utc",
            name="uq_alarm_item_start",
        ),
        CheckConstraint(
            "status IN ('pending','sent','skipped','failed')",
            name="ck_alarm_status",
        ),
        Index("ix_alarm_status_start", "status", "scheduled_start_utc"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day_plan_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("day_plan_items.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("week_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    scheduled_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TimeboxCheckin(Base):
    __tablename__ = "timebox_checkins"
    __table_args__ = (
        CheckConstraint(
            "checkin_type IN ('task_overrun','panic_10m')", name="ck_timebox_type"
        ),
        CheckConstraint(
            "status IN ('pending','sent','cancelled','skipped')", name="ck_timebox_status"
        ),
        Index("ix_timebox_status_due", "status", "due_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    checkin_type: Mapped[str] = mapped_column(String(16), nullable=False)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("week_tasks.id", ondelete="SET NULL")
    )
    day_plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("day_plan_items.id", ondelete="SET NULL")
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SwitchConnectionState(Base):
    __tablename__ = "switch_connection_state"

    agent_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(80), nullable=False)
    generation: Mapped[str | None] = mapped_column(String(80))
    highest_processed_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    protocol_revision: Mapped[str | None] = mapped_column(String(80))
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessedSwitchEvent(Base):
    __tablename__ = "processed_switch_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('ignored','replied','proposal_created','approval_applied',"
            "'failed','processing')",
            name="ck_processed_events_outcome",
        ),
    )

    agent_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    event_sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(80), nullable=False)
    room_id: Mapped[str] = mapped_column(String(120), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(240))
    message_id: Mapped[str | None] = mapped_column(String(240))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)


ALL_MODELS: tuple[Any, ...] = (
    OwnerConfig,
    YearGoal,
    MonthCommitment,
    FixedEvent,
    WeekPlacement,
    WeekTask,
    DayPlan,
    DayPlanItem,
    PendingProposal,
    PlanningScopeRevision,
    ReminderDispatch,
    AuditEvent,
    ModelUsageRecord,
    AlarmDispatch,
    TimeboxCheckin,
    SwitchConnectionState,
    ProcessedSwitchEvent,
)
