"""Bounded Execution Sub-Agent for dashboard-delegated tasks.

This is deliberately not part of the seven-tool chat surface. It receives one
existing task, produces a single deliverable, and never mutates planning state.
The owner triggers it from the token-gated dashboard.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.integrations.openrouter.client import LLMError, OpenRouterClient
from zasky.integrations.openrouter.usage import CostGuard

logger = logging.getLogger(__name__)


class ExecutionSubAgentError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


_SYSTEM_PROMPT = """You are Zasky's Execution Sub-Agent.

You are the Execution Agent. You have been given the Task, its parent
Commitment, and the Year Goal. Use this context to ensure your output is highly
specific and relevant to the user's overarching goals.

You may only:
- draft copy;
- write code snippets;
- outline plans;
- format documents.

You cannot browse the web, access external services, modify a database, send
messages, run commands, or read secrets. Never claim to have done any of those
things. Work on exactly one owner-selected task, use only the task details,
parent context and owner instruction supplied, and do not invent new tasks or
approvals.

If the context is insufficient to complete the task well, state exactly what is
missing in your Verification Checklist.

ALWAYS return structured Markdown with exactly these three second-level
headings, in this order:

## 1. The Deliverable

The directly usable draft, snippet, outline, or formatted document.

## 2. What I Did

A short factual description of the work you performed. Do not claim external
actions.

## 3. Verification Checklist

- [ ] A concrete check the owner can perform.
- [ ] Another concrete check where useful.

If the task is ambiguous, state the smallest clarification needed inside the
deliverable and still make the most useful safe assumption."""
_USER_PROMPT = """Execute the task using the context above and the required
three-section Markdown format. Do not invent context that is not present."""


def build_execution_context(
    task: dict[str, Any], instruction: str | None
) -> str:
    """Build the owner-scoped context block supplied to the Execution Agent."""
    owner_instruction = (instruction or "").strip()[:2000]
    lines = [
        f"Task title: {task.get('title', 'Untitled task')}",
        f"Task estimate: {task.get('est_min', 'unknown')} minutes",
        f"Scheduled date: {task.get('scheduled_date', 'unknown')}",
        f"Task status: {task.get('status', 'unknown')}",
        f"Parent month commitment: {task.get('commitment_title') or 'Not linked'}",
    ]
    if task.get("commitment_priority"):
        lines.append(f"Commitment priority: {task['commitment_priority']}")
    if task.get("commitment_deadline"):
        lines.append(f"Commitment deadline: {task['commitment_deadline']}")
    if task.get("commitment_consequence"):
        lines.append(f"Commitment consequence: {task['commitment_consequence']}")
    lines.extend(
        [
            f"Parent year goal: {task.get('goal_title') or 'Not linked'}",
            (
                "Year goal evidence of done: "
                f"{task.get('goal_evidence_of_done') or 'Not provided'}"
            ),
            f"Existing resume note: {task.get('resume_note') or 'None'}",
            "Owner instructions: "
            + (owner_instruction or "No additional instructions supplied."),
        ]
    )
    return "\n".join(lines)


def ensure_structured_output(output: str) -> str:
    """Guarantee the two-step UI can always render the three required sections."""
    required = (
        "## 1. The Deliverable",
        "## 2. What I Did",
        "## 3. Verification Checklist",
    )
    normalized = output.strip()
    if all(marker in normalized for marker in required):
        return normalized
    return (
        f"{required[0]}\n\n{normalized}\n\n"
        f"{required[1]}\n\n"
        "The sub-agent produced the deliverable above from the supplied task "
        "details. No external tools or database changes were used.\n\n"
        f"{required[2]}\n\n"
        "- [ ] Review the deliverable for accuracy and tone.\n"
        "- [ ] Confirm it matches the task scope.\n"
        "- [ ] Approve execution or request a revision."
    )


class ExecutionSubAgent:
    def __init__(
        self,
        settings: Settings,
        llm: OpenRouterClient,
        cost_guard: CostGuard,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._cost = cost_guard

    async def run(
        self,
        *,
        task: dict[str, Any],
        instruction: str | None = None,
    ) -> dict[str, Any]:
        correlation_id = uuid.uuid4().hex
        try:
            await self._cost.check()
        except DomainError as exc:
            raise ExecutionSubAgentError(
                exc.code, exc.message, retryable=exc.retryable
            ) from exc

        context = build_execution_context(task, instruction)
        messages = [
            {
                "role": "system",
                "content": (
                    f"{_SYSTEM_PROMPT}\n\n"
                    "--- OWNER-SCOPED TASK CONTEXT ---\n"
                    f"{context}"
                ),
            },
            {"role": "user", "content": _USER_PROMPT},
        ]
        try:
            response = await self._llm.chat(messages)
        except LLMError as exc:
            await self._cost.record_failure(correlation_id=correlation_id)
            raise ExecutionSubAgentError(
                exc.code, exc.message, retryable=exc.retryable
            ) from exc
        except Exception as exc:
            await self._cost.record_failure(correlation_id=correlation_id)
            logger.exception(
                "Execution Sub-Agent failed",
                extra={
                    "component": "execution",
                    "error_code": type(exc).__name__,
                },
            )
            raise ExecutionSubAgentError(
                "EXECUTION_FAILED",
                "The execution sub-agent failed before producing a result.",
            ) from exc

        await self._cost.record(response, correlation_id=correlation_id)
        output = ensure_structured_output(response.content.strip())
        if not output:
            raise ExecutionSubAgentError(
                "EXECUTION_EMPTY",
                "The execution sub-agent returned no content.",
            )
        return {
            "output": output,
            "model": self._settings.openai_model,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
        }
