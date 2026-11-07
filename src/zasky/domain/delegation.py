"""Durable human-in-the-loop delegation proposals and execution sign-off."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select

from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.domain.schemas import CompleteTaskRequest
from zasky.domain.service import normalize_title
from zasky.storage.database import Database
from zasky.storage.models import (
    AuditEvent,
    DelegationProposal,
    PendingProposal,
    WeekPlacement,
    WeekTask,
)

if TYPE_CHECKING:
    from zasky.domain.service import DomainService

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_DELEGATION_TRIGGER_RE = re.compile(
    r"\b(?:can't|cannot|can not|won't be able to|will not be able to|"
    r"am not able to|don't have time for|do not have time for|"
    r"not going to finish|running out of time for|at risk)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "be",
    "can",
    "cannot",
    "cant",
    "complete",
    "do",
    "doing",
    "finish",
    "for",
    "get",
    "have",
    "i",
    "in",
    "is",
    "it",
    "my",
    "not",
    "now",
    "of",
    "on",
    "out",
    "risk",
    "running",
    "task",
    "the",
    "this",
    "time",
    "to",
    "today",
    "tomorrow",
    "will",
    "work",
    "won't",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_title(text).split()
        if token not in _STOPWORDS and len(token) > 1
    }


class DelegationService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._db = database
        self._settings = settings

    @staticmethod
    def looks_like_trigger(text: str) -> bool:
        return _DELEGATION_TRIGGER_RE.search(text) is not None

    async def _new_code(self, session: Any) -> str:
        for _ in range(40):
            code = "ZK-" + "".join(
                secrets.choice(_CODE_ALPHABET) for _ in range(4)
            )
            pending = await session.scalar(
                select(PendingProposal.id).where(PendingProposal.code == code)
            )
            delegation = await session.scalar(
                select(DelegationProposal.id).where(
                    or_(
                        DelegationProposal.code == code,
                        DelegationProposal.execution_code == code,
                    )
                )
            )
            if pending is None and delegation is None:
                return code
        raise DomainError("CONFLICT", "Could not generate a delegation code.")

    async def _audit(
        self,
        session: Any,
        *,
        action: str,
        entity_id: str | None,
        summary: str,
        actor_id: str | None,
    ) -> None:
        session.add(
            AuditEvent(
                id=str(uuid.uuid4()),
                actor_type="owner" if actor_id else "system",
                actor_id=actor_id,
                action=action,
                entity_type="delegation",
                entity_id=entity_id,
                summary_redacted=summary[:300],
                correlation_id=uuid.uuid4().hex,
            )
        )

    async def propose(self, task_id: str) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            task = await session.get(WeekTask, task_id)
            if task is None:
                raise DomainError("NOT_FOUND", "That task does not exist.")
            if task.status in {"completed", "cancelled"}:
                raise DomainError(
                    "CONFLICT",
                    "A completed or cancelled task cannot be delegated.",
                )
            existing = await session.scalar(
                select(DelegationProposal).where(
                    DelegationProposal.task_id == task_id,
                    DelegationProposal.status.in_(
                        ("pending", "running", "awaiting_signoff")
                    ),
                )
            )
            if existing is not None:
                return {
                    "code": existing.code,
                    "task_id": task.id,
                    "task_title": task.title,
                    "status": existing.status,
                    "execution_code": existing.execution_code,
                }
            now = _now()
            proposal = DelegationProposal(
                id=str(uuid.uuid4()),
                code=await self._new_code(session),
                task_id=task.id,
                status="pending",
                expires_at=now + timedelta(minutes=30),
            )
            session.add(proposal)
            await self._audit(
                session,
                action="delegation_proposed",
                entity_id=proposal.id,
                summary="delegation proposed",
                actor_id=self._settings.owner_switch_participant_id,
            )
            await session.commit()
            return {
                "code": proposal.code,
                "task_id": task.id,
                "task_title": task.title,
                "status": "pending",
                "execution_code": None,
            }

    async def find_task_from_text(self, text: str) -> dict[str, Any] | None:
        phrase = normalize_title(text)
        phrase_tokens = _tokens(text)
        if not phrase_tokens:
            return None
        async with self._db.locked_session() as session:
            tasks = (
                await session.execute(
                    select(WeekTask)
                    .join(
                        WeekPlacement,
                        WeekTask.placement_id == WeekPlacement.id,
                    )
                    .where(
                        WeekTask.status.in_(("active", "parked")),
                        WeekPlacement.status == "active",
                    )
                    .order_by(WeekTask.scheduled_date, WeekTask.created_at)
                )
            ).scalars().all()

        scored: list[tuple[float, WeekTask]] = []
        for task in tasks:
            title = normalize_title(task.title)
            title_tokens = _tokens(task.title)
            if not title_tokens:
                continue
            overlap = len(title_tokens & phrase_tokens) / len(title_tokens)
            if title in phrase or phrase in title:
                overlap = 1.0
            if overlap >= 0.6:
                scored.append((overlap, task))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        task = scored[0][1]
        return {"id": task.id, "title": task.title}

    async def start(
        self, code: str, *, actor_id: str
    ) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            proposal = await session.scalar(
                select(DelegationProposal).where(
                    DelegationProposal.code == code.upper()
                )
            )
            if proposal is None:
                raise DomainError(
                    "NOT_FOUND", "That delegation proposal does not exist."
                )
            task = await session.get(WeekTask, proposal.task_id)
            if task is None:
                raise DomainError("NOT_FOUND", "That task no longer exists.")
            if proposal.status == "awaiting_signoff":
                return {
                    "proposal_id": proposal.id,
                    "task_id": proposal.task_id,
                    "task_title": task.title,
                    "execution_code": proposal.execution_code,
                    "output_markdown": proposal.output_markdown,
                    "already": "awaiting_signoff",
                }
            if proposal.status == "completed":
                return {
                    "proposal_id": proposal.id,
                    "task_id": proposal.task_id,
                    "task_title": task.title,
                    "execution_code": proposal.execution_code,
                    "already": "completed",
                }
            if proposal.status == "running":
                return {
                    "proposal_id": proposal.id,
                    "task_id": proposal.task_id,
                    "task_title": task.title,
                    "execution_code": proposal.execution_code,
                    "already": "running",
                }
            if proposal.status != "pending":
                raise DomainError(
                    "CONFLICT",
                    f"That delegation proposal is already {proposal.status}.",
                )
            now = _now()
            if _aware(proposal.expires_at) <= now:
                proposal.status = "expired"
                proposal.resolved_at = now
                proposal.resolution_actor = actor_id
                await session.commit()
                raise DomainError(
                    "PROPOSAL_EXPIRED",
                    "That delegation proposal expired. Nothing changed.",
                )
            if task.status in {"completed", "cancelled"}:
                raise DomainError(
                    "CONFLICT",
                    "A completed or cancelled task cannot be delegated.",
                )
            proposal.status = "running"
            proposal.execution_code = await self._new_code(session)
            proposal.resolution_actor = actor_id
            await session.commit()
            return {
                "proposal_id": proposal.id,
                "task_id": proposal.task_id,
                "task_title": task.title,
                "execution_code": proposal.execution_code,
                "output_markdown": None,
                "already": None,
            }

    async def mark_awaiting_signoff(
        self, execution_code: str, output_markdown: str
    ) -> None:
        async with self._db.locked_session() as session:
            proposal = await session.scalar(
                select(DelegationProposal).where(
                    DelegationProposal.execution_code == execution_code
                )
            )
            if proposal is None:
                raise DomainError(
                    "NOT_FOUND", "That execution proposal does not exist."
                )
            proposal.status = "awaiting_signoff"
            proposal.output_markdown = output_markdown
            proposal.error_code = None
            await session.commit()

    async def mark_failed(self, execution_code: str, error_code: str) -> None:
        async with self._db.locked_session() as session:
            proposal = await session.scalar(
                select(DelegationProposal).where(
                    DelegationProposal.execution_code == execution_code
                )
            )
            if proposal is not None:
                proposal.status = "failed"
                proposal.error_code = error_code[:60]
                proposal.resolved_at = _now()
                await session.commit()

    async def get_by_execution_code(
        self, execution_code: str
    ) -> DelegationProposal | None:
        async with self._db.locked_session() as session:
            return await session.scalar(
                select(DelegationProposal).where(
                    DelegationProposal.execution_code == execution_code.upper()
                )
            )

    async def approve_execution(
        self,
        execution_code: str,
        *,
        actor_id: str,
        domain: DomainService,
    ) -> dict[str, Any]:
        async with self._db.locked_session() as session:
            proposal = await session.scalar(
                select(DelegationProposal).where(
                    DelegationProposal.execution_code == execution_code.upper()
                )
            )
            if proposal is None:
                raise DomainError(
                    "NOT_FOUND", "That execution proposal does not exist."
                )
            task = await session.get(WeekTask, proposal.task_id)
            if task is None:
                raise DomainError("NOT_FOUND", "That task no longer exists.")
            if proposal.status == "completed":
                return {
                    "ok": True,
                    "task_id": proposal.task_id,
                    "task_title": task.title,
                    "status": task.status,
                    "already": "completed",
                }
            if proposal.status != "awaiting_signoff":
                raise DomainError(
                    "CONFLICT",
                    "The execution is not awaiting owner sign-off.",
                )
            proposal_id = proposal.id
            task_id = proposal.task_id
            task_title = task.title

        result = await domain.complete_task(
            CompleteTaskRequest(task_id=task_id)
        )
        async with self._db.locked_session() as session:
            proposal = await session.get(DelegationProposal, proposal_id)
            if proposal is not None:
                proposal.status = "completed"
                proposal.resolved_at = _now()
                proposal.resolution_actor = actor_id
                await self._audit(
                    session,
                    action="execution_approved",
                    entity_id=proposal.id,
                    summary="execution approved and task completed",
                    actor_id=actor_id,
                )
                await session.commit()
        return {
            "ok": True,
            "task_id": task_id,
            "task_title": task_title,
            "status": result.get("status", "completed"),
            "already": result.get("already"),
        }
