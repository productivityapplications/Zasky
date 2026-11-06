from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from zasky.config import Settings
from zasky.integrations.openrouter.client import (
    LLMError,
    OpenRouterClient,
    chat_tool_definitions,
)


def configured(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "openai_api_key": SecretStr("test-key"),
            "openai_base_url": "https://openrouter.test/api/v1",
            "openai_model": "openai/gpt-4o-mini",
            "openai_max_input_tokens": 24000,
            "openai_max_output_tokens": 2000,
        }
    )


@pytest.mark.asyncio
async def test_chat_completions_response_is_typed(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-4o-mini"
        assert body["max_tokens"] == 2000
        return httpx.Response(
            200,
            json={
                "id": "req-1",
                "choices": [
                    {
                        "message": {
                            "content": "Ready.",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "query",
                                        "arguments": '{"state":"week"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 15},
            },
        )

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test/api/v1",
    )
    client = OpenRouterClient(configured(settings), client=http)
    try:
        response = await client.chat(
            [{"role": "user", "content": "status"}], tools=[]
        )
        assert response.content == "Ready."
        assert response.tool_calls[0].name == "query"
        assert response.prompt_tokens == 120
        assert response.completion_tokens == 15
        assert response.provider_request_id == "req-1"
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_auth_failure_is_safe(settings: Settings) -> None:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": "bad key"})
        ),
        base_url="https://openrouter.test/api/v1",
    )
    client = OpenRouterClient(configured(settings), client=http)
    try:
        with pytest.raises(LLMError) as exc:
            await client.chat([{"role": "user", "content": "hi"}])
        assert exc.value.code == "MODEL_UNAVAILABLE"
        assert "test-key" not in str(exc.value)
    finally:
        await http.aclose()


def test_chat_tool_definitions_has_exactly_seven() -> None:
    tools = chat_tool_definitions()
    assert len(tools) == 7
    assert {tool["function"]["name"] for tool in tools} == {
        "add_commitment",
        "place_week",
        "plan_day",
        "reconcile",
        "park_task",
        "complete_task",
        "query",
    }
