"""SQLite operational state for the Switch connection and event ledger.

Phase 1 intentionally keeps only the state needed to resume safely and avoid
duplicate replies. The full domain schema arrives in Phase 2 with Alembic.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from sqlalchemy import event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from zasky.config import Settings, normalize_database_url
from zasky.storage.models import Base, ProcessedSwitchEvent, SwitchConnectionState


def _serialized(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Serialize SQLite access for the single-writer process.

    SQLite permits one writer and aiosqlite connections are not safe to
    interleave across concurrent sessions on the same in-memory database. The
    application is single-writer by design, so a process-local lock is both
    simpler and safer than relying on pool behaviour.
    """

    @wraps(fn)
    async def wrapper(self: Database, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            return await fn(self, *args, **kwargs)

    return wrapper


class ClaimResult:
    """Outcome of trying to claim an event for processing."""

    __slots__ = ("is_new", "existing_outcome")

    def __init__(self, is_new: bool, existing_outcome: str | None = None) -> None:
        self.is_new = is_new
        self.existing_outcome = existing_outcome


class Database:
    """Async SQLite database with WAL, foreign keys and a bounded busy timeout."""

    def __init__(self, url: str) -> None:
        url = normalize_database_url(url)
        self.url = url
        parsed = make_url(url)
        self._is_sqlite = parsed.drivername.startswith("sqlite")
        self._is_postgres = parsed.drivername.startswith("postgresql")
        self._is_memory = self._is_sqlite and parsed.database in (
            None,
            "",
            ":memory:",
        )
        self._engine = create_async_engine(
            url,
            echo=False,
            future=True,
            pool_pre_ping=self._is_postgres,
            poolclass=StaticPool if self._is_memory else None,
            # Neon uses a PgBouncer-style pooler. Server-side prepared
            # statements can survive a migration and then fail with
            # "cached statement plan is invalid"; disabling the asyncpg
            # statement cache keeps the pooler compatible.
            connect_args=(
                {"prepared_statement_cache_size": 0} if self._is_postgres else {}
            ),
        )
        if self._is_sqlite and not self._is_memory:
            event.listen(self._engine.sync_engine, "connect", self._set_sqlite_pragmas)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )
        self._lock = asyncio.Lock()

    @staticmethod
    def _set_sqlite_pragmas(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        return cls(settings.database_url)

    @_serialized
    async def init(self) -> None:
        if self._is_sqlite and not self._is_memory:
            parsed = make_url(self.url)
            database_path = parsed.database
            if database_path:
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        if self._is_sqlite:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        # Postgres schema is owned by Alembic; the app checks alembic_version
        # during startup and refuses readiness if migrations are incomplete.

    @_serialized
    async def close(self, *, close_connections: bool = True) -> None:
        await self._engine.dispose(close=close_connections)

    @_serialized
    async def healthcheck(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @_serialized
    async def get_schema_revision(self) -> str | None:
        try:
            async with self._engine.connect() as connection:
                result = await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
                return result.scalar_one_or_none()
        except (OperationalError, ProgrammingError):
            return None

    @asynccontextmanager
    async def locked_session(self) -> AsyncIterator[AsyncSession]:
        """A session serialized with the process-wide SQLite lock."""
        async with self._lock:
            async with self._session_factory() as session:
                yield session

    @_serialized
    async def get_connection_state(self, agent_id: str) -> SwitchConnectionState | None:
        async with self._session_factory() as session:
            return await session.get(SwitchConnectionState, agent_id)

    @_serialized
    async def save_connection_state(
        self,
        *,
        agent_id: str,
        connection_id: str,
        generation: str | None,
        protocol_revision: str | None,
        cursor: int,
        connected_at: datetime | None = None,
    ) -> None:
        async with self._session_factory() as session:
            state = await session.get(SwitchConnectionState, agent_id)
            if state is None:
                state = SwitchConnectionState(
                    agent_id=agent_id,
                    connection_id=connection_id,
                    generation=generation,
                    highest_processed_sequence=cursor,
                    protocol_revision=protocol_revision,
                    last_connected_at=connected_at or datetime.now(UTC),
                )
                session.add(state)
            else:
                state.connection_id = connection_id
                state.generation = generation
                state.highest_processed_sequence = max(
                    state.highest_processed_sequence, cursor
                )
                state.protocol_revision = protocol_revision
                state.last_connected_at = connected_at or datetime.now(UTC)
                state.updated_at = datetime.now(UTC)
            await session.commit()

    @_serialized
    async def advance_cursor(
        self,
        *,
        agent_id: str,
        connection_id: str,
        sequence: int,
        generation: str | None = None,
        protocol_revision: str | None = None,
    ) -> None:
        """Advance the durable cursor without creating a domain write."""
        async with self._session_factory() as session:
            state = await session.get(SwitchConnectionState, agent_id)
            if state is None:
                state = SwitchConnectionState(
                    agent_id=agent_id,
                    connection_id=connection_id,
                    generation=generation,
                    highest_processed_sequence=sequence,
                    protocol_revision=protocol_revision,
                    last_connected_at=datetime.now(UTC),
                )
                session.add(state)
            else:
                state.connection_id = connection_id
                state.generation = generation or state.generation
                state.protocol_revision = protocol_revision or state.protocol_revision
                state.highest_processed_sequence = max(
                    state.highest_processed_sequence, sequence
                )
                state.updated_at = datetime.now(UTC)
            await session.commit()

    @_serialized
    async def claim_event(
        self,
        *,
        agent_id: str,
        sequence: int,
        connection_id: str,
        room_id: str,
        sender_id: str | None,
        message_id: str | None,
        correlation_id: str,
    ) -> ClaimResult:
        """Insert an event claim; returns whether this caller owns processing."""
        async with self._session_factory() as session:
            session.add(
                ProcessedSwitchEvent(
                    agent_id=agent_id,
                    event_sequence=sequence,
                    connection_id=connection_id,
                    room_id=room_id,
                    sender_id=sender_id,
                    message_id=message_id,
                    outcome="processing",
                    correlation_id=correlation_id,
                )
            )
            try:
                await session.commit()
                return ClaimResult(True)
            except IntegrityError:
                await session.rollback()
                existing = await session.get(
                    ProcessedSwitchEvent, (agent_id, sequence)
                )
                return ClaimResult(
                    False, existing.outcome if existing is not None else None
                )

    @_serialized
    async def finish_event(
        self,
        *,
        agent_id: str,
        sequence: int,
        connection_id: str,
        outcome: str,
        generation: str | None = None,
        protocol_revision: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(ProcessedSwitchEvent, (agent_id, sequence))
            if row is not None:
                row.outcome = outcome
                row.processed_at = datetime.now(UTC)
            state = await session.get(SwitchConnectionState, agent_id)
            if state is None:
                state = SwitchConnectionState(
                    agent_id=agent_id,
                    connection_id=connection_id,
                    generation=generation,
                    highest_processed_sequence=sequence,
                    protocol_revision=protocol_revision,
                    last_connected_at=datetime.now(UTC),
                )
                session.add(state)
            else:
                state.connection_id = connection_id
                state.generation = generation or state.generation
                state.protocol_revision = protocol_revision or state.protocol_revision
                state.highest_processed_sequence = max(
                    state.highest_processed_sequence, sequence
                )
                state.updated_at = datetime.now(UTC)
            await session.commit()

    @_serialized
    async def get_event_outcome(self, agent_id: str, sequence: int) -> str | None:
        async with self._session_factory() as session:
            row = await session.get(ProcessedSwitchEvent, (agent_id, sequence))
            return row.outcome if row is not None else None

    @_serialized
    async def pending_event_count(self, agent_id: str) -> int:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ProcessedSwitchEvent).where(
                    ProcessedSwitchEvent.agent_id == agent_id,
                    ProcessedSwitchEvent.outcome == "processing",
                )
            )
            return len(result.scalars().all())

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session
