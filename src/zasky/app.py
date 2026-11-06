"""Process composition: health server, Switch client and single-writer lock."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from zasky.access.approvals import ApprovalCommand
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
            )
        self.switch = SwitchClient(
            settings,
            self.db,
            self.ops,
            message_handler=(
                self.orchestrator.handle_message if self.orchestrator else None
            ),
            approval_handler=self._handle_approval,
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

    async def stop(self) -> None:
        logger.info("Zasky stopping", extra={"component": "app"})
        await self.switch.close()
        if self._health_server is not None:
            self._health_server.should_exit = True
        for task in (self._switch_task, self._health_task):
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
            return (f"{exc.message} (code: {exc.code})", "failed")
        code = result.get("proposal", command.code or "proposal")
        if result.get("status") == "approved":
            return (
                f"Approved {code}. The change is now stored. "
                f"Approve {code} / Reject {code}",
                "approval_applied",
            )
        if result.get("status") == "rejected":
            return (
                f"Rejected {code}. No planning changes were applied.",
                "approval_applied",
            )
        if result.get("already") == "approved":
            return (
                f"{code} was already approved. No further changes were made.",
                "approval_applied",
            )
        return (f"Resolved {code}. No further changes were made.", "approval_applied")

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self.start()
        try:
            await stop.wait()
        finally:
            await self.stop()
