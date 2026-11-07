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
            "commitment_priority": "high",
            "commitment_deadline": "2026-11-08",
            "goal_title": "Deliver the hackathon demo",
            "goal_evidence_of_done": "A reviewed 150-second demo.",
            "resume_note": "Stopped after the opening hook.",
            "status": "active",
        },
        instruction="Make it 90 seconds long.",
    )
    assert result["output"].startswith("## 1. The Deliverable")
    assert "## 2. What I Did" in result["output"]
    assert "## 3. Verification Checklist" in result["output"]
    assert "Draft deliverable: first section." in result["output"]
    assert result["prompt_tokens"] == 120
    assert cost.checked == 1
    assert len(cost.recorded) == 1
    assert len(llm.messages) == 2
    system_prompt = llm.messages[0]["content"]
    assert "Execution Agent" in system_prompt
    assert "## 1. The Deliverable" in system_prompt
    assert "browse" in system_prompt
    assert "Draft the demo script" in system_prompt
    assert "Produce the demo" in system_prompt
    assert "Deliver the hackathon demo" in system_prompt
    assert "A reviewed 150-second demo." in system_prompt
    assert "Stopped after the opening hook." in system_prompt
    assert "Make it 90 seconds long." in system_prompt
    assert "If the context is insufficient" in system_prompt


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
