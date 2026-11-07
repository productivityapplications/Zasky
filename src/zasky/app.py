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
from zasky.agent.execution import ExecutionSubAgent, ExecutionSubAgentError
from zasky.agent.orchestrator import AgentOrchestrator
from zasky.config import Settings
from zasky.domain.delegation import DelegationService
from zasky.domain.errors import DomainError
from zasky.domain.schemas import QueryRequest
from zasky.domain.service import DomainService
from zasky.integrations.discord import (
    DiscordNotificationError,
    DiscordNotifier,
)
from zasky.integrations.openrouter.client import OpenRouterClient
from zasky.integrations.openrouter.usage import CostGuard
from zasky.ops.dashboard_api import create_dashboard_app
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


def _escape_md(text: str) -> str:
    escaped = str(text).replace("\\", "\\\\")
    for char in ("*", "_", "`", "~", "|"):
        escaped = escaped.replace(char, "\\" + char)
    return escaped


class ZaskyApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database.from_settings(settings)
        self.ops = SwitchOperations(settings)
        self.domain = DomainService(self.db, settings)
        self.delegations = DelegationService(self.db, settings)
        self.briefing = BriefingBuilder(self.db, settings)
        self.discord = DiscordNotifier(settings)
        self.alarm_scheduler = AlarmScheduler(self.db, self.ops, settings)
        self.llm: OpenRouterClient | None = None
        self.orchestrator: AgentOrchestrator | None = None
        self.execution: ExecutionSubAgent | None = None
        self.cost_guard: CostGuard | None = None
        if settings.llm_enabled:
            self.llm = OpenRouterClient(settings)
            self.cost_guard = CostGuard(self.db, settings)
            self.orchestrator = AgentOrchestrator(
                settings,
                self.domain,
                self.llm,
                ContextBuilder(self.db, settings),
                self.cost_guard,
                history_provider=self._recent_room_history,
            )
            self.execution = ExecutionSubAgent(
                settings, self.llm, self.cost_guard
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
        self.dashboard_app = create_dashboard_app(self)

        parsed_database = make_url(settings.database_url)
        database_path = parsed_database.database
        if (
            parsed_database.drivername.startswith("sqlite")
            and database_path
            and database_path != ":memory:"
        ):
            lock_path = Path(database_path).with_suffix(".lock")
        else:
            # Postgres has no local database file. The container's /tmp is a
            # writable tmpfs while the application root is read-only.
            lock_path = Path("/tmp/zasky.lock")
        self._lock = SingleWriterLock(lock_path)

        self._health_server: uvicorn.Server | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._dashboard_server: uvicorn.Server | None = None
        self._dashboard_task: asyncio.Task[None] | None = None
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
        if (
            self.settings.dashboard_api_key is not None
            and self.settings.dashboard_api_key.get_secret_value().strip()
        ):
            dashboard_config = uvicorn.Config(
                self.dashboard_app,
                host=self.settings.dashboard_bind_host,
                port=self.settings.dashboard_port,
                log_config=None,
                access_log=False,
                lifespan="off",
            )
            self._dashboard_server = uvicorn.Server(dashboard_config)
            setattr(self._dashboard_server, signal_hook, lambda: None)
            self._dashboard_task = asyncio.create_task(
                self._dashboard_server.serve(), name="zasky-dashboard"
            )
            logger.info(
                "Owner dashboard API started",
                extra={"component": "dashboard"},
            )
        else:
            logger.error(
                "Owner dashboard API disabled: DASHBOARD_API_KEY is not set",
                extra={
                    "component": "dashboard",
                    "error_code": "DASHBOARD_API_DISABLED",
                },
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
        if self._dashboard_server is not None:
            self._dashboard_server.should_exit = True
        for task in (
            self._switch_task,
            self._health_task,
            self._dashboard_task,
            self._alarm_task,
        ):
            if task is None:
                continue
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._switch_task = None
        self._health_task = None
        self._dashboard_task = None
        if self.llm is not None:
            await self.llm.close()
        await self.discord.close()
        await self.db.close()
        await self.ops.close()
        self._lock.release()

    async def _post_daily_briefing(self, local_date: str) -> str:
        try:
            from datetime import date as date_type

            briefing = await self.briefing.build(date_type.fromisoformat(local_date))
            delivered = False
            try:
                delivered = await self.discord.send_daily_briefing(
                    briefing, local_date
                )
            except DiscordNotificationError as exc:
                logger.error(
                    "Daily briefing channel delivery failed",
                    extra={
                        "component": "discord",
                        "error_code": exc.code,
                    },
                )
            if not delivered:
                # Keep the staging flow usable until the operator adds the
                # channel IDs and bot token to the protected environment.
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
            if delivered:
                return (
                    "\n\n📅 **Daily Briefing posted to "
                    "`#daily-briefings`.**"
                )
            return (
                "\n\n📅 **Daily Briefing posted in the main room.** "
                "Configure `DISCORD_DAILY_BRIEFINGS_CHANNEL_ID` to route it "
                "to `#daily-briefings`."
            )
        except Exception:
            logger.exception(
                "Daily briefing post failed",
                extra={"component": "briefing", "error_code": "BRIEFING_FAILED"},
            )
            return "\n\nThe plan is stored, but the Daily Briefing post failed."

    async def _post_reconcile_summary(
        self, code: str, applied: dict[str, object]
    ) -> str:
        local_date = applied.get("date")
        if not isinstance(local_date, str):
            return ""
        items: list[dict[str, object]] = []
        try:
            result = await self.domain.query(
                QueryRequest(state="today", horizon=local_date)
            )
            raw_items = result.get("items", [])
            if isinstance(raw_items, list):
                items = [
                    item for item in raw_items if isinstance(item, dict)
                ]
        except Exception:
            logger.warning(
                "Recovery summary detail query failed",
                extra={
                    "component": "discord",
                    "error_code": "RECONCILE_DETAIL_FAILED",
                },
            )
        feasibility = applied.get("feasibility")
        moves = applied.get("moves")
        try:
            delivered = await self.discord.send_reconcile_summary(
                code=code,
                local_date=local_date,
                items=items,
                moves=moves if isinstance(moves, int) else 0,
                feasibility=(
                    str(feasibility) if feasibility is not None else None
                ),
            )
        except DiscordNotificationError as exc:
            logger.error(
                "Reconcile summary channel delivery failed",
                extra={
                    "component": "discord",
                    "error_code": exc.code,
                },
            )
            return (
                "\n\nRecovery applied, but the `#reconcile-alerts` "
                "summary was not posted."
            )
        if delivered:
            return "\n\n♻️ **Recovery summary posted to `#reconcile-alerts`.**"
        return (
            "\n\nRecovery applied. Configure "
            "`DISCORD_RECONCILE_ALERTS_CHANNEL_ID` to post the summary to "
            "`#reconcile-alerts`."
        )

    async def publish_execution_result(
        self,
        *,
        title: str,
        body: str,
        task_id: str | None = None,
    ) -> bool:
        """Delivery hook for the Execution Sub-Agent."""
        return await self.discord.send_execution_result(
            title=title,
            body=body,
            task_id=task_id,
        )

    async def delegate_task(
        self,
        task_id: str,
        instruction: str | None = None,
        execution_code: str | None = None,
    ) -> dict[str, object]:
        """Run the bounded Execution Sub-Agent for one owner-selected task."""
        if self.execution is None:
            raise ExecutionSubAgentError(
                "MODEL_UNAVAILABLE",
                "The execution sub-agent needs a configured model.",
            )
        task = await self.domain.task_detail(task_id)
        if task["status"] in {"completed", "cancelled"}:
            raise ExecutionSubAgentError(
                "CONFLICT",
                "A completed or cancelled task cannot be delegated.",
            )
        result = await self.execution.run(task=task, instruction=instruction)
        output = str(result["output"])
        if execution_code:
            await self.delegations.mark_awaiting_signoff(
                execution_code, output
            )
        delivered = False
        try:
            body = (
                self._execution_signoff(output, execution_code)
                if execution_code
                else output
            )
            delivered = await self.publish_execution_result(
                title=str(task["title"]),
                body=body,
                task_id=task_id,
            )
        except DiscordNotificationError as exc:
            logger.error(
                "Execution result channel delivery failed",
                extra={
                    "component": "discord",
                    "error_code": exc.code,
                },
            )
        return {
            "task_id": task_id,
            "title": task["title"],
            "output": output,
            "model": result["model"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "discord_delivered": delivered,
            "execution_code": execution_code,
        }

    @staticmethod
    def _execution_signoff(output: str, execution_code: str | None) -> str:
        if not execution_code:
            return output
        return (
            f"{output}\n\n---\n"
            "**Please review the deliverable above.** If this meets your "
            "standards, reply "
            f"`approve execution {execution_code}` to mark the task complete."
        )

    async def delegate_from_dashboard(
        self, task_id: str, instruction: str | None = None
    ) -> dict[str, object]:
        """Start the same two-step delegation flow from the owner dashboard."""
        if self.execution is None:
            raise ExecutionSubAgentError(
                "MODEL_UNAVAILABLE",
                "The execution sub-agent needs a configured model.",
            )
        proposal = await self.delegations.propose(task_id)
        started = await self.delegations.start(
            str(proposal["code"]),
            actor_id=self.settings.owner_switch_participant_id,
        )
        if started.get("already") == "awaiting_signoff":
            return {
                "task_id": task_id,
                "title": started.get("task_title"),
                "output": started.get("output_markdown"),
                "execution_code": started.get("execution_code"),
                "discord_delivered": False,
                "already": "awaiting_signoff",
            }
        if started.get("already") == "completed":
            return {
                "task_id": task_id,
                "title": started.get("task_title"),
                "output": "",
                "execution_code": started.get("execution_code"),
                "discord_delivered": False,
                "already": "completed",
            }
        execution_code = str(started["execution_code"])
        try:
            return await self.delegate_task(
                task_id, instruction, execution_code=execution_code
            )
        except ExecutionSubAgentError as exc:
            await self.delegations.mark_failed(execution_code, exc.code)
            raise

    async def approve_execution(self, execution_code: str) -> dict[str, object]:
        return await self.delegations.approve_execution(
            execution_code,
            actor_id=self.settings.owner_switch_participant_id,
            domain=self.domain,
        )

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
        delegation_offer = await self._maybe_offer_delegation(
            event.data.payload.body
        )
        if delegation_offer is not None:
            return delegation_offer
        return await self.orchestrator.handle_message(event)

    async def _maybe_offer_delegation(self, text: str) -> str | None:
        """Create a deterministic delegation proposal when the owner is stuck."""
        if not self.delegations.looks_like_trigger(text):
            return None
        task = await self.delegations.find_task_from_text(text)
        if task is None:
            return None
        try:
            proposal = await self.delegations.propose(str(task["id"]))
        except DomainError:
            return None
        title = _escape_md(str(task["title"]))
        if proposal["status"] == "awaiting_signoff" and proposal["execution_code"]:
            return (
                f"The execution for **{title}** is already ready. "
                f"Reply `approve execution {proposal['execution_code']}` "
                "to mark it complete."
            )
        if proposal["status"] == "running":
            return (
                f"The execution for **{title}** is already running. "
                "I will post the deliverable in `#ai-workspace` when it is ready."
            )
        return (
            f"You don't have time for **{title}**. Should I delegate this to "
            "the Execution Agent? Reply "
            f"`delegate {proposal['code']}`."
        )

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
        if command.action == "delegate":
            return await self._handle_delegate_command(command, event)
        if command.action == "approve_execution":
            return await self._handle_execution_approval(command, event)
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
            applied = result.get("applied", {})
            if result.get("proposal_type") == "day":
                local_date = applied.get("date") if isinstance(applied, dict) else None
                if isinstance(local_date, str):
                    note = await self._post_daily_briefing(local_date)
            elif result.get("proposal_type") == "reconcile":
                if isinstance(applied, dict):
                    note = await self._post_reconcile_summary(code, applied)
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

    async def _handle_delegate_command(
        self, command: ApprovalCommand, event: MessageEvent
    ) -> tuple[str, str]:
        if command.code is None:
            return ("A delegation code is required. Nothing changed.", "failed")
        if self.execution is None:
            return (
                "The Execution Agent needs a configured model. Nothing changed.",
                "failed",
            )
        try:
            started = await self.delegations.start(
                command.code, actor_id=event.data.payload.sender
            )
        except DomainError as exc:
            return (
                f"⚠️ **Not started**\n\n{exc.message}\n\n"
                f"*Code: `{exc.code}`*",
                "failed",
            )
        if started.get("already") == "completed":
            return (
                f"ℹ️ **Already completed** `{command.code}`\n\n"
                "No further changes were made.",
                "approval_applied",
            )
        if started.get("already") == "running":
            return (
                f"ℹ️ **Execution already running** `{command.code}`\n\n"
                "I will post the deliverable in `#ai-workspace`.",
                "approval_applied",
            )
        if started.get("already") == "awaiting_signoff":
            code = str(started.get("execution_code") or "ZK-????")
            return (
                f"ℹ️ **Execution already ready** `{code}`\n\n"
                "Review the deliverable in `#ai-workspace` and reply "
                f"`approve execution {code}` to mark the task complete.",
                "approval_applied",
            )
        execution_code = str(started["execution_code"])
        task_id = str(started["task_id"])
        task_title = _escape_md(str(started["task_title"]))
        try:
            result = await self.delegate_task(
                task_id, execution_code=execution_code
            )
        except ExecutionSubAgentError as exc:
            await self.delegations.mark_failed(execution_code, exc.code)
            return (
                f"⚠️ **Execution failed** `{execution_code}`\n\n"
                f"{exc.message}\n\nNothing changed.",
                "failed",
            )
        if not result.get("discord_delivered"):
            fallback = self._execution_signoff(
                str(result["output"]), execution_code
            )
            try:
                await self.ops.post_message(fallback)
            except Exception:
                logger.exception(
                    "Execution fallback post failed",
                    extra={
                        "component": "delegation",
                        "error_code": "EXECUTION_FALLBACK_FAILED",
                    },
                )
        destination = (
            "`#ai-workspace`"
            if result.get("discord_delivered")
            else "this room (workspace delivery failed)"
        )
        return (
            f"✅ **Execution ready** `{execution_code}`\n\n"
            f"The structured deliverable for **{task_title}** is in "
            f"{destination}.\n\n"
            "Review it and reply "
            f"`approve execution {execution_code}` to mark the task complete.",
            "approval_applied",
        )

    async def _handle_execution_approval(
        self, command: ApprovalCommand, event: MessageEvent
    ) -> tuple[str, str]:
        if command.code is None:
            return ("An execution code is required. Nothing changed.", "failed")
        try:
            result = await self.delegations.approve_execution(
                command.code,
                actor_id=event.data.payload.sender,
                domain=self.domain,
            )
        except DomainError as exc:
            return (
                f"⚠️ **Not completed**\n\n{exc.message}\n\n"
                f"*Code: `{exc.code}`*",
                "failed",
            )
        if result.get("already") == "completed":
            return (
                f"ℹ️ **Already approved** `{command.code}`\n\n"
                "The task was already complete.",
                "approval_applied",
            )
        title = _escape_md(str(result.get("task_title") or "Task"))
        return (
            f"✅ **Execution approved** `{command.code}`\n\n"
            f"**Task:** {title}\n"
            "The task is marked complete.",
            "approval_applied",
        )

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self.start()
        try:
            await stop.wait()
        finally:
            await self.stop()
