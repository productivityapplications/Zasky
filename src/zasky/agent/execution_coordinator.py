"""Scope-aware execution coordinator used by chat and dashboard delegation."""

from __future__ import annotations

import logging
from typing import Any

from zasky.agent.execution import ExecutionSubAgent, ExecutionSubAgentError
from zasky.config import Settings
from zasky.domain.delegation import DelegationService
from zasky.domain.service import DomainService
from zasky.integrations.discord import DiscordNotificationError, DiscordNotifier

logger = logging.getLogger(__name__)


class ExecutionCoordinator:
    def __init__(
        self,
        *,
        settings: Settings,
        domain: DomainService,
        delegations: DelegationService,
        execution: ExecutionSubAgent | None,
        discord: DiscordNotifier,
    ) -> None:
        self._settings = settings
        self._domain = domain
        self._delegations = delegations
        self._execution = execution
        self._discord = discord

    async def delegate_task(
        self,
        task_id: str,
        instruction: str | None = None,
        execution_code: str | None = None,
    ) -> dict[str, Any]:
        if self._execution is None:
            raise ExecutionSubAgentError(
                "MODEL_UNAVAILABLE",
                "The execution sub-agent needs a configured model.",
            )
        task = await self._domain.task_detail(task_id)
        if task["status"] in {"completed", "cancelled"}:
            raise ExecutionSubAgentError(
                "CONFLICT",
                "A completed or cancelled task cannot be delegated.",
            )
        if task["execution_type"] != "ai":
            raise ExecutionSubAgentError(
                "HUMAN_TASK",
                "This task requires your physical presence, I cannot delegate it.",
            )
        result = await self._execution.run(task=task, instruction=instruction)
        output = str(result["output"])
        if execution_code:
            await self._delegations.mark_awaiting_signoff(
                execution_code, output
            )
        delivered = False
        try:
            body = (
                self._execution_signoff(output, execution_code)
                if execution_code
                else output
            )
            delivered = await self._discord.send_execution_result(
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

    async def delegate_from_dashboard(
        self, task_id: str, instruction: str | None = None
    ) -> dict[str, Any]:
        if self._execution is None:
            raise ExecutionSubAgentError(
                "MODEL_UNAVAILABLE",
                "The execution sub-agent needs a configured model.",
            )
        proposal = await self._delegations.propose(task_id)
        started = await self._delegations.start(
            str(proposal["code"]),
            actor_id=self._settings.owner_switch_participant_id,
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
        if started.get("already") == "running":
            raise ExecutionSubAgentError(
                "CONFLICT",
                "An execution is already running for this task.",
            )
        execution_code = str(started["execution_code"])
        try:
            return await self.delegate_task(
                task_id, instruction, execution_code=execution_code
            )
        except ExecutionSubAgentError as exc:
            await self._delegations.mark_failed(execution_code, exc.code)
            raise

    async def approve_execution(self, execution_code: str) -> dict[str, Any]:
        return await self._delegations.approve_execution(
            execution_code,
            actor_id=self._settings.owner_switch_participant_id,
            domain=self._domain,
        )

    def start(self, proposal_code: str, actor_id: str) -> Any:
        return self._delegations.start(proposal_code, actor_id=actor_id)

    async def mark_failed(self, execution_code: str, error_code: str) -> None:
        await self._delegations.mark_failed(execution_code, error_code)

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
