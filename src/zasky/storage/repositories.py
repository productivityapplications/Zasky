"""Small repository boundaries for Phase 2 state.

Domain services in Phase 3 may add richer repositories, but these keep owner
configuration, audit evidence and optimistic-concurrency scopes centralized.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from zasky.config import Settings
from zasky.storage.database import Database
from zasky.storage.models import AuditEvent, OwnerConfig, PlanningScopeRevision


class OwnerConfigRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def ensure_seeded(self, settings: Settings) -> OwnerConfig:
        """Create the singleton owner row from validated settings if absent."""
        async with self._db.locked_session() as session:
            existing = await session.get(OwnerConfig, 1)
            if existing is not None:
                return existing
            config = OwnerConfig(
                id=1,
                owner_switch_participant_id=settings.owner_switch_participant_id,
                allowed_room_id=settings.switch_room_id,
                timezone=settings.timezone,
                capacity_pct=settings.capacity_pct,
                week_start_weekday=settings.week_start_day,
                daily_task_limit=settings.daily_task_limit,
                transition_buffer_min=settings.transition_buffer_min,
                morning_prep_min=settings.morning_prep_min,
                commute_buffer_min=settings.commute_buffer_min,
                availability_json=settings.weekly_availability_json,
                morning_prompt_time=settings.morning_prompt_time,
                evening_prompt_time=settings.evening_prompt_time,
                reminders_enabled=settings.reminders_enabled,
                timebox_checkins_enabled=settings.timebox_checkins_enabled,
                revision=1,
            )
            session.add(config)
            await session.commit()
            await session.refresh(config)
            return config

    async def get(self) -> OwnerConfig | None:
        async with self._db.locked_session() as session:
            return await session.get(OwnerConfig, 1)


class AuditRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def record(
        self,
        *,
        actor_type: str,
        actor_id: str | None,
        action: str,
        entity_type: str | None,
        entity_id: str | None,
        summary_redacted: str,
        correlation_id: str,
    ) -> str:
        event_id = str(uuid4())
        async with self._db.locked_session() as session:
            session.add(
                AuditEvent(
                    id=event_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    summary_redacted=summary_redacted,
                    correlation_id=correlation_id,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
        return event_id


class ScopeRevisionRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def get_or_create(self, scope_key: str) -> int:
        async with self._db.locked_session() as session:
            revision = await session.get(PlanningScopeRevision, scope_key)
            if revision is not None:
                return revision.revision
            session.add(
                PlanningScopeRevision(
                    scope_key=scope_key,
                    revision=1,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()
            return 1

    async def increment(self, scope_key: str) -> int:
        async with self._db.locked_session() as session:
            revision = await session.get(PlanningScopeRevision, scope_key)
            if revision is None:
                revision = PlanningScopeRevision(
                    scope_key=scope_key,
                    revision=1,
                    updated_at=datetime.now(UTC),
                )
                session.add(revision)
            else:
                revision.revision += 1
                revision.updated_at = datetime.now(UTC)
            await session.commit()
            return revision.revision

    async def all_for(self, scope_keys: list[str]) -> dict[str, int]:
        if not scope_keys:
            return {}
        async with self._db.locked_session() as session:
            rows = (
                await session.execute(
                    select(PlanningScopeRevision).where(
                        PlanningScopeRevision.scope_key.in_(scope_keys)
                    )
                )
            ).scalars()
            return {row.scope_key: row.revision for row in rows}
