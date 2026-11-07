"""Process composition: health server, Switch client and single-writer lock."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from zasky.access.approvals import ApprovalCommand, is_conversational_approval
from zasky.agent.briefing import BriefingBuilder
from zasky.agent.context import ContextBuilder
from zasky.agent.orchestrator import AgentOrchestrator
from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.domain.service import DomainService
from zasky.integrations.openrouter.client import OpenRouterClient
from zasky.integrations.openrouter.usage import CostGuard
from zasky.ops.health import create_health_app
from zasky.ops.lock import SingleWriterLock
from zasky.ops.maintenance import head_revision
from zasky.scheduler.alarms import AlarmScheduler
from zasky.storage.database import Database
from zasky.storage.repositories import OwnerConfigRepository
from zasky.switch.client import SwitchClient
from zasky.switch.events import MessageEvent
from zasky.switch.operations import SwitchOperations

logger = logging.getLogger(__name__)


class ZaskyApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database.from_settings(settings)
        self.ops = SwitchOperations(settings)
        self.domain = DomainService(self.db, settings)
        self.briefing = BriefingBuilder(self.db, settings)
        self.alarm_scheduler = AlarmScheduler(self.db, self.ops, settings)
        self.llm: OpenRouterClient | None = None
        self.orchestrator: AgentOrchestrator | None = None
        if settings.llm_enabled:
            self.llm = OpenRouterClient(settings)
            self.orchestrator = AgentOrchestrator(
                settings,
                self.domain,
                self.llm,
                ContextBuilder(self.db, settings),
                CostGuard(self.db, settings),
                history_provider=self._recent_room_history,
            )
        self.switch = SwitchClient(
            settings,
            self.db,
            self.ops,
            message_handler=(
                self._handle_message if self.orchestrator else None
            ),
            approval_handler=self._handle_approval,
            typing_placeholder=settings.typing_placeholder_enabled,
        )
        self.health_app = create_health_app(self)

        database_path = make_url(settings.database_url).database
        if database_path and database_path != ":memory:":
            lock_path = Path(database_path).with_suffix(".lock")
        else:
            lock_path = Path("/tmp/zasky.lock")
        self._lock = SingleWriterLock(lock_path)

        self._health_server: uvicorn.Server | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._switch_task: asyncio.Task[None] | None = None
        self._alarm_task: asyncio.Task[None] | None = None
        self.schema_revision: str | None = None
        self.schema_ready = False

    async def start(self) -> None:
        self._lock.acquire()
        await self.db.init()
        self.schema_revision = await self.db.get_schema_revision()
        expected = head_revision()
        self.schema_ready = expected is not None and self.schema_revision == expected
        if not self.schema_ready:
            logger.error(
                "Database schema is not at the migration head",
                extra={
                    "component": "app",
                    "error_code": "SCHEMA_NOT_CURRENT",
                },
            )
        else:
            await OwnerConfigRepository(self.db).ensure_seeded(self.settings)
        logger.info(
            "Zasky starting",
            extra={"component": "app"},
        )

        config = uvicorn.Config(
            self.health_app,
            host=self.settings.health_bind_host,
            port=self.settings.health_bind_port,
            log_config=None,
            access_log=False,
            lifespan="off",
        )
        self._health_server = uvicorn.Server(config)
        # Signal handling belongs to __main__, not to the embedded server.
        signal_hook = "install_signal_handlers"
        setattr(self._health_server, signal_hook, lambda: None)
        self._health_task = asyncio.create_task(
            self._health_server.serve(), name="zasky-health"
        )
        self._switch_task = asyncio.create_task(self.switch.run(), name="zasky-switch")
        self._alarm_task = asyncio.create_task(
            self.alarm_scheduler.run(), name="zasky-alarms"
        )

    async def stop(self) -> None:
        logger.info("Zasky stopping", extra={"component": "app"})
        await self.switch.close()
        await self.alarm_scheduler.stop()
        if self._health_server is not None:
            self._health_server.should_exit = True
        for task in (self._switch_task, self._health_task, self._alarm_task):
            if task is None:
                continue
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._switch_task = None
        self._health_task = None
        if self.llm is not None:
            await self.llm.close()
        await self.db.close()
        await self.ops.close()
        self._lock.release()

    async def _post_daily_briefing(self, local_date: str) -> str:
        try:
            from datetime import date as date_type

            briefing = await self.briefing.build(date_type.fromisoformat(local_date))
            await self.ops.post_message(briefing)
            try:
                await self.ops.create_room_document(
                    name=f"Daily Briefing — {local_date}",
                    description="Zasky daily briefing",
                    instructions="Read this for the approved plan of the day.",
                    content=briefing,
                )
            except Exception:
                logger.warning(
                    "Daily briefing document creation failed",
                    extra={
                        "component": "briefing",
                        "error_code": "BRIEFING_DOCUMENT_FAILED",
                    },
                )
            return (
                "\n\n📅 **Daily Briefing posted.** "
                "Switch 0.31.0 has no pin operation; pin the message in Discord "
                "if you want it at the top."
            )
        except Exception:
            logger.exception(
                "Daily briefing post failed",
                extra={"component": "briefing", "error_code": "BRIEFING_FAILED"},
            )
            return "\n\nThe plan is stored, but the Daily Briefing post failed."

    async def _handle_message(self, event: MessageEvent) -> str:
        if self.orchestrator is None:
            return "The model is not configured. Nothing changed."
        if is_conversational_approval(event.data.payload.body):
            codes = await self.domain.pending_codes()
            if codes:
                code = sorted(codes)[0]
                return (
                    "I cannot accept conversational approvals. Please reply with "
                    f"`approve {code}` to lock this in."
                )
        return await self.orchestrator.handle_message(event)

    async def _recent_room_history(self) -> list[dict[str, object]]:
        context = await self.ops.read_context(limit=20)
        threads = context.get("threads", [])
        entries: list[dict[str, object]] = []
        if isinstance(threads, list):
            for thread in threads:
                if not isinstance(thread, dict):
                    continue
                root = thread.get("root")
                if isinstance(root, dict):
                    entries.append(root)
                replies = thread.get("replies", [])
                if isinstance(replies, list):
                    entries.extend(item for item in replies if isinstance(item, dict))
        def timestamp(item: dict[str, object]) -> int:
            value = item.get("timestamp", 0)
            return int(value) if isinstance(value, (int, float, str)) else 0

        entries.sort(key=timestamp)
        messages: list[dict[str, object]] = []
        for entry in entries:
            if entry.get("kind") != "message":
                continue
            body = str(entry.get("body", "")).strip()
            if not body:
                continue
            messages.append(
                {
                    "sender_name": str(entry.get("sender_name") or "participant"),
                    "body": body[:500],
                    "timestamp": entry.get("timestamp"),
                }
            )
        return messages[-10:]

    @property
    def model_ready(self) -> bool:
        return self.orchestrator is not None

    async def _handle_approval(
        self, command: ApprovalCommand, event: MessageEvent
    ) -> tuple[str, str]:
        try:
            result = await self.domain.resolve_proposal(
                action=command.action,
                code=command.code,
                actor_id=event.data.payload.sender,
                room_id=event.data.room_id,
            )
        except DomainError as exc:
            return (
                f"⚠️ **Not applied**\n\n{exc.message}\n\n"
                f"*Code: `{exc.code}`*",
                "failed",
            )
        code = result.get("proposal", command.code or "proposal")
        if result.get("status") == "approved":
            note = ""
            if result.get("proposal_type") == "day":
                applied = result.get("applied", {})
                local_date = applied.get("date") if isinstance(applied, dict) else None
                if isinstance(local_date, str):
                    note = await self._post_daily_briefing(local_date)
            return (
                f"✅ **Approved** `{code}`\n\n"
                "Your plan change is now stored." + note,
                "approval_applied",
            )
        if result.get("status") == "rejected":
            return (
                f"🚫 **Rejected** `{code}`\n\n"
                "No planning changes were applied.",
                "approval_applied",
            )
        if result.get("already") == "approved":
            return (
                f"ℹ️ **Already approved** `{code}`\n\n"
                "No further changes were made.",
                "approval_applied",
            )
        return (
            f"ℹ️ **Resolved** `{code}`\n\nNo further changes were made.",
            "approval_applied",
        )

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self.start()
        try:
            await stop.wait()
        finally:
            await self.stop()
