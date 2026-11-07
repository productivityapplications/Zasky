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

You may only:
- draft copy;
- write code snippets;
- outline plans;
- format documents.

You cannot browse the web, access external services, modify a database, send
messages, run commands, or read secrets. Never claim to have done any of those
things. Work on exactly one owner-selected task, use only the task details and
owner instruction supplied, and do not invent new tasks or approvals.

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
_USER_PROMPT = """Task: {title}
Estimate: {est_min} minutes
Scheduled: {scheduled_date}
Commitment: {commitment}
Status: {status}

Owner instruction:
{instruction}

Produce the deliverable now using the required three-section Markdown format."""


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

        prompt = _USER_PROMPT.format(
            title=task.get("title", "Untitled task"),
            est_min=task.get("est_min", "unknown"),
            scheduled_date=task.get("scheduled_date", "unknown"),
            commitment=task.get("commitment_title") or "None",
            status=task.get("status", "unknown"),
            instruction=(instruction or "No extra instruction supplied.").strip(),
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
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
