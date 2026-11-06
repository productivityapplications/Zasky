"""HTTP operations exposed by a Switch agent connection."""

from __future__ import annotations

from typing import Any

import httpx

from zasky.config import Settings


class SwitchOperationsError(RuntimeError):
    """A Switch operation failed without exposing private response content."""


class SwitchOperations:
    """Minimal typed wrapper around the documented agent operations."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._agent_id = settings.switch_agent_id
        self._connection_id = settings.switch_connection_id
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.switch_base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {settings.switch_agent_api_key.get_secret_value()}",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post_operation(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(
                f"/agents/{self._agent_id}/ops/{operation}",
                json=payload,
                headers={"X-Switch-Connection-Id": self._connection_id},
            )
        except httpx.HTTPError as exc:
            raise SwitchOperationsError(
                f"{operation} transport error: {type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise SwitchOperationsError(
                f"{operation} failed with HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SwitchOperationsError(f"{operation} returned non-JSON") from exc
        if isinstance(body, dict) and isinstance(body.get("result"), dict):
            return body["result"]
        if isinstance(body, dict):
            return body
        raise SwitchOperationsError(f"{operation} returned an unexpected payload")

    async def connect_to_room(self, room_id: str) -> dict[str, Any]:
        return await self._post_operation(
            "connect_to_room",
            {"room_id": room_id, "include_general_instructions": False},
        )

    async def read_context(self, *, limit: int = 20, room_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"limit": limit}
        if room_id is not None:
            payload["room_id"] = room_id
        return await self._post_operation("read_context", payload)

    async def post_message(self, body: str, *, thread_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"body": body}
        if thread_id is not None:
            payload["thread_id"] = thread_id
        return await self._post_operation("post_message", payload)
