"""OpenRouter Chat Completions client.

The operator explicitly selected OpenRouter's OpenAI-compatible endpoint and
`openai/gpt-4o-mini` for the hackathon build. This adapter is deliberately
small: strict messages/tools in, typed tool calls/usage out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from zasky.config import Settings
from zasky.domain.schemas import TOOL_DEFINITIONS


class LLMError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider_request_id: str | None = None
    usage_known: bool = True


def chat_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in TOOL_DEFINITIONS
    ]


class OpenRouterClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(settings.llm_request_timeout_seconds),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if not self._settings.openai_api_key:
            raise LLMError("MODEL_UNAVAILABLE", "No model credential is configured.")
        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": self._settings.openai_max_output_tokens,
        }
        if tools:
            payload["tools"] = chat_tool_definitions() if tools is TOOL_DEFINITIONS else tools
            payload["tool_choice"] = "auto"
        if self._settings.openai_store:
            payload["store"] = True

        headers = {
            "Authorization": (
                "Bearer " + self._settings.openai_api_key.get_secret_value()
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "https://localhost/zasky",
            "X-Title": "Zasky",
        }
        try:
            response = await self._client.post(
                "/chat/completions", json=payload, headers=headers
            )
            # OpenRouter/OpenAI-compatible providers may not accept `store` on
            # Chat Completions. Retry once without it only for that known shape.
            if response.status_code == 400 and "store" in response.text.lower():
                payload.pop("store", None)
                response = await self._client.post(
                    "/chat/completions", json=payload, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise LLMError(
                "MODEL_UNAVAILABLE", "The model provider timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                "MODEL_UNAVAILABLE", "The model provider is unreachable."
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise LLMError("MODEL_UNAVAILABLE", "The model credential was rejected.")
        if response.status_code == 429:
            raise LLMError(
                "RATE_LIMITED", "The model provider rate-limited this request.",
                retryable=True,
            )
        if response.status_code >= 500:
            raise LLMError(
                "MODEL_UNAVAILABLE", "The model provider is temporarily unavailable.",
                retryable=True,
            )
        if response.status_code >= 400:
            raise LLMError("MODEL_UNAVAILABLE", "The model request was rejected.")
        try:
            body = response.json()
        except ValueError as exc:
            raise LLMError("MODEL_UNAVAILABLE", "The model returned an invalid response.") from exc

        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise LLMError("MODEL_UNAVAILABLE", "The model returned no choices.")
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        raw_calls = message.get("tool_calls") or []
        calls: list[ToolCall] = []
        if isinstance(raw_calls, list):
            for raw in raw_calls:
                if not isinstance(raw, dict):
                    continue
                function = raw.get("function", {})
                if not isinstance(function, dict):
                    continue
                call_id = raw.get("id") or function.get("name") or "call"
                name = function.get("name") or ""
                arguments = function.get("arguments") or "{}"
                calls.append(
                    ToolCall(
                        id=str(call_id),
                        name=str(name),
                        arguments=arguments if isinstance(arguments, str) else "{}",
                    )
                )
        usage = body.get("usage") if isinstance(body, dict) else None
        prompt_tokens = int(usage.get("prompt_tokens", 0)) if isinstance(usage, dict) else 0
        completion_tokens = (
            int(usage.get("completion_tokens", 0)) if isinstance(usage, dict) else 0
        )
        return LLMResponse(
            content=content.strip(),
            tool_calls=calls,
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            provider_request_id=(
                str(body.get("id"))
                if isinstance(body, dict) and body.get("id")
                else None
            ),
            usage_known=isinstance(usage, dict),
        )
