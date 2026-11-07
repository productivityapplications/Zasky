from __future__ import annotations

from typing import Any

import pytest

from zasky.agent.execution import ExecutionSubAgent, ExecutionSubAgentError
from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.integrations.openrouter.client import LLMError, LLMResponse


class FakeCostGuard:
    def __init__(self) -> None:
        self.checked = 0
        self.recorded: list[LLMResponse] = []
        self.failures = 0
        self.check_error: DomainError | None = None

    async def check(self) -> None:
        self.checked += 1
        if self.check_error is not None:
            raise self.check_error

    async def record(
        self,
        response: LLMResponse,
        *,
        correlation_id: str,
        status: str = "succeeded",
    ) -> None:
        self.recorded.append(response)

    async def record_failure(self, *, correlation_id: str) -> None:
        self.failures += 1


class FakeLLM:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.error: LLMError | None = None

    async def chat(self, messages: list[dict[str, Any]], **_: Any) -> LLMResponse:
        self.messages = messages
        if self.error is not None:
            raise self.error
        return LLMResponse(
            content="Draft deliverable: first section.",
            prompt_tokens=120,
            completion_tokens=40,
            provider_request_id="req-1",
        )


@pytest.mark.asyncio
async def test_execution_subagent_produces_bounded_output(settings: Settings) -> None:
    llm = FakeLLM()
    cost = FakeCostGuard()
    agent = ExecutionSubAgent(settings, llm, cost)  # type: ignore[arg-type]
    result = await agent.run(
        task={
            "title": "Draft the demo script",
            "est_min": 45,
            "scheduled_date": "2026-11-06",
            "commitment_title": "Produce the demo",
            "status": "active",
        },
        instruction="Make it 90 seconds long.",
    )
    assert result["output"].startswith("Draft deliverable")
    assert result["prompt_tokens"] == 120
    assert cost.checked == 1
    assert len(cost.recorded) == 1
    assert len(llm.messages) == 2
    assert "Execution Sub-Agent" in llm.messages[0]["content"]
    assert "Draft the demo script" in llm.messages[1]["content"]
    assert "Make it 90 seconds long." in llm.messages[1]["content"]


@pytest.mark.asyncio
async def test_execution_subagent_respects_cost_guard(settings: Settings) -> None:
    llm = FakeLLM()
    cost = FakeCostGuard()
    cost.check_error = DomainError("BUDGET_EXCEEDED", "Budget exceeded.")
    agent = ExecutionSubAgent(settings, llm, cost)  # type: ignore[arg-type]
    with pytest.raises(ExecutionSubAgentError) as excinfo:
        await agent.run(task={"title": "Task", "status": "active"})
    assert excinfo.value.code == "BUDGET_EXCEEDED"
    assert llm.messages == []


@pytest.mark.asyncio
async def test_execution_subagent_surfaces_provider_failure(
    settings: Settings,
) -> None:
    llm = FakeLLM()
    llm.error = LLMError("MODEL_UNAVAILABLE", "Provider unavailable.")
    cost = FakeCostGuard()
    agent = ExecutionSubAgent(settings, llm, cost)  # type: ignore[arg-type]
    with pytest.raises(ExecutionSubAgentError) as excinfo:
        await agent.run(task={"title": "Task", "status": "active"})
    assert excinfo.value.code == "MODEL_UNAVAILABLE"
    assert cost.failures == 1
