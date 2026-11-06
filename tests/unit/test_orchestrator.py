from __future__ import annotations

import asyncio
import json

import pytest
import pytest_asyncio
from pydantic import SecretStr

from tests.fixtures.identities import OWNER_ID, ROOM_ID
from zasky.agent.context import ContextBuilder
from zasky.agent.orchestrator import AgentOrchestrator
from zasky.config import Settings
from zasky.domain.service import DomainService
from zasky.integrations.openrouter.client import LLMError, LLMResponse, ToolCall
from zasky.integrations.openrouter.usage import CostGuard
from zasky.storage.database import Database
from zasky.storage.repositories import OwnerConfigRepository
from zasky.switch.events import MessageEvent

AVAILABILITY = (
    '{"monday": [{"start": "09:00", "end": "21:00"}], '
    '"tuesday": [{"start": "09:00", "end": "21:00"}], '
    '"wednesday": [{"start": "09:00", "end": "21:00"}], '
    '"thursday": [{"start": "09:00", "end": "21:00"}], '
    '"friday": [{"start": "09:00", "end": "21:00"}], '
    '"saturday": [{"start": "09:00", "end": "21:00"}], '
    '"sunday": [{"start": "09:00", "end": "21:00"}]}'
)


def planned(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "weekly_availability_json": AVAILABILITY,
            "openai_api_key": SecretStr("test-key"),
            "openai_model": "openai/gpt-4o-mini",
            "openai_max_input_tokens": 24000,
            "openai_max_output_tokens": 2000,
            "max_llm_requests_per_day": 100,
            "max_llm_spend_usd_month": 20.0,
        }
    )


class FakeLLM:
    def __init__(self, *responses: LLMResponse | Exception) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.messages: list[list[dict]] = []

    async def chat(self, messages, tools=None) -> LLMResponse:
        self.calls += 1
        self.messages.append(messages)
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def event(body: str) -> MessageEvent:
    return MessageEvent.model_validate(
        {
            "event": "message",
            "id": 1,
            "data": {
                "type": "message",
                "room_id": ROOM_ID,
                "payload": {
                    "addressed": True,
                    "sender": OWNER_ID,
                    "sender_name": "Owner",
                    "message_id": "m1",
                    "body": body,
                },
                "sequence": 1,
            },
        }
    )


def goal_call(call_id: str, title: str = "Ship the plan") -> ToolCall:
    return ToolCall(
        id=call_id,
        name="add_commitment",
        arguments=json.dumps(
            {
                "operation": "create",
                "entry_type": "year_goal",
                "title": title,
                "year": 2027,
                "evidence_of_done": "A dated review note",
            }
        ),
    )


@pytest_asyncio.fixture
async def orchestrator_env(tmp_path, settings: Settings):
    configured = planned(settings)
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await db.init()
    await OwnerConfigRepository(db).ensure_seeded(configured)
    try:
        yield db, configured
    finally:
        await db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_plain_answer_does_not_require_tools(orchestrator_env) -> None:
    db, settings = orchestrator_env
    llm = FakeLLM(LLMResponse(content="Hello from Zasky", usage_known=False))
    orch = AgentOrchestrator(
        settings,
        DomainService(db, settings),
        llm,  # type: ignore[arg-type]
        ContextBuilder(db, settings),
        CostGuard(db, settings),
    )
    reply = await orch.handle_message(event("hello"))
    assert reply == "Hello from Zasky"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_tool_proposal_is_pending_and_code_is_shown(orchestrator_env) -> None:
    db, settings = orchestrator_env
    llm = FakeLLM(
        LLMResponse(
            content="",
            tool_calls=[goal_call("call-1")],
            prompt_tokens=10,
            completion_tokens=5,
            usage_known=True,
        ),
        LLMResponse(
            content="I prepared the goal.",
            prompt_tokens=10,
            completion_tokens=5,
            usage_known=True,
        ),
    )
    domain = DomainService(db, settings)
    orch = AgentOrchestrator(
        settings, domain, llm, ContextBuilder(db, settings), CostGuard(db, settings)  # type: ignore[arg-type]
    )
    reply = await orch.handle_message(event("make a goal to ship the plan"))
    assert "Proposal ZK-" in reply
    from sqlalchemy import select

    from zasky.storage.models import PendingProposal, YearGoal

    async with db.locked_session() as session:
        proposals = (await session.execute(select(PendingProposal))).scalars().all()
        goals = (await session.execute(select(YearGoal))).scalars().all()
    assert len(proposals) == 1
    assert goals == []
    approved = await domain.resolve_proposal(
        action="approve",
        code=proposals[0].code,
        actor_id=OWNER_ID,
        room_id=ROOM_ID,
    )
    assert approved["status"] == "approved"


@pytest.mark.asyncio
async def test_invalid_tool_arguments_twice_do_not_write(orchestrator_env) -> None:
    db, settings = orchestrator_env
    bad = ToolCall(
        id="call-1", name="add_commitment", arguments='{"operation":"create"}'
    )
    llm = FakeLLM(
        LLMResponse(content="", tool_calls=[bad], usage_known=False),
        LLMResponse(content="", tool_calls=[bad], usage_known=False),
    )
    orch = AgentOrchestrator(
        settings,
        DomainService(db, settings),
        llm,  # type: ignore[arg-type]
        ContextBuilder(db, settings),
        CostGuard(db, settings),
    )
    reply = await orch.handle_message(event("make a goal"))
    assert "couldn't validate" in reply
    from sqlalchemy import select

    from zasky.storage.models import PendingProposal, YearGoal

    async with db.locked_session() as session:
        assert (await session.execute(select(PendingProposal))).scalars().all() == []
        assert (await session.execute(select(YearGoal))).scalars().all() == []


@pytest.mark.asyncio
async def test_at_most_two_proposals_per_message(orchestrator_env) -> None:
    db, settings = orchestrator_env
    calls = [
        goal_call("call-1", "First goal"),
        goal_call("call-2", "Second goal"),
        goal_call("call-3", "Third goal"),
    ]
    llm = FakeLLM(
        LLMResponse(content="", tool_calls=calls, usage_known=False),
        LLMResponse(content="I prepared two proposals.", usage_known=False),
    )
    orch = AgentOrchestrator(
        settings,
        DomainService(db, settings),
        llm,  # type: ignore[arg-type]
        ContextBuilder(db, settings),
        CostGuard(db, settings),
    )
    reply = await orch.handle_message(event("make three goals"))
    assert reply.count("Proposal ZK-") == 2
    from sqlalchemy import select

    from zasky.storage.models import PendingProposal

    async with db.locked_session() as session:
        assert len((await session.execute(select(PendingProposal))).scalars().all()) == 2


@pytest.mark.asyncio
async def test_provider_failure_is_transparent(orchestrator_env) -> None:
    db, settings = orchestrator_env
    llm = FakeLLM(LLMError("MODEL_UNAVAILABLE", "down"))
    orch = AgentOrchestrator(
        settings,
        DomainService(db, settings),
        llm,  # type: ignore[arg-type]
        ContextBuilder(db, settings),
        CostGuard(db, settings),
    )
    reply = await orch.handle_message(event("hello"))
    assert "temporarily unavailable" in reply
    assert "No planning data" in reply or "did not change" in reply


def test_status_intent_guard() -> None:
    assert AgentOrchestrator._explicit_status_intent(
        "mark this task done", "complete_task", "{}"
    )
    assert not AgentOrchestrator._explicit_status_intent(
        "what is left this week", "complete_task", "{}"
    )
    assert AgentOrchestrator._explicit_status_intent(
        "park it for now", "park_task", '{"action":"park"}'
    )


@pytest.mark.asyncio
async def test_hallucinated_code_is_rejected(orchestrator_env) -> None:
    db, settings = orchestrator_env
    llm = FakeLLM(
        LLMResponse(
            content="Proposal ZK-XXXX. Nothing is changed until approval.",
            usage_known=False,
        )
    )
    orch = AgentOrchestrator(
        settings,
        DomainService(db, settings),
        llm,  # type: ignore[arg-type]
        ContextBuilder(db, settings),
        CostGuard(db, settings),
    )
    reply = await orch.handle_message(event("make a plan"))
    assert "ZK-XXXX" not in reply
    assert "couldn't create a valid proposal" in reply


def test_argument_normalizer_fills_redundant_month_fields(orchestrator_env) -> None:
    _db, settings = orchestrator_env
    orch = AgentOrchestrator(
        settings,
        DomainService(_db, settings),
        FakeLLM(LLMResponse(content="unused")),  # type: ignore[arg-type]
        ContextBuilder(_db, settings),
        CostGuard(_db, settings),
    )
    args = orch._normalize_arguments(
        "add_commitment",
        {
            "entry_type": "month_commitment",
            "deadline_local_date": "2026-11-08",
            "title": "Synthetic commitment",
        },
    )
    assert args["year"] == 2026
    assert args["month"] == 11
    assert args["priority"] == "normal"


@pytest.mark.asyncio
async def test_recent_room_history_is_included(orchestrator_env) -> None:
    db, settings = orchestrator_env
    llm = FakeLLM(LLMResponse(content="Understood.", usage_known=False))

    async def history():
        return [
            {"sender_name": "Owner", "body": "I have 45 minutes", "timestamp": 1},
            {"sender_name": "Owner", "body": "What is my plan for Friday?", "timestamp": 2},
        ]

    orch = AgentOrchestrator(
        settings,
        DomainService(db, settings),
        llm,  # type: ignore[arg-type]
        ContextBuilder(db, settings),
        CostGuard(db, settings),
        history_provider=history,
    )
    await orch.handle_message(event("should I lock that in?"))
    context_prompt = llm.messages[0][2]["content"]
    assert "recent_room_messages" in context_prompt
    assert "I have 45 minutes" in context_prompt


def test_prompt_has_conversational_approval_guard() -> None:
    from zasky.agent.orchestrator import load_system_prompt

    prompt = load_system_prompt()
    assert "I cannot accept conversational approvals" in prompt
    assert "call `plan_day`" in prompt
    assert "Never calculate the calendar date yourself" in prompt
