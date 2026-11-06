from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from zasky.ops.health import create_health_app


class FakeDB:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    async def healthcheck(self) -> bool:
        return self.healthy


class FakeSwitch:
    def __init__(self, ready: bool) -> None:
        self.is_ready = ready


async def request(app: Any, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_liveness_is_always_ok() -> None:
    app = create_health_app(
        SimpleNamespace(db=FakeDB(True), switch=FakeSwitch(True), schema_ready=True)
    )
    response = await request(app, "/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_requires_database_and_switch() -> None:
    app = create_health_app(
        SimpleNamespace(db=FakeDB(True), switch=FakeSwitch(True), schema_ready=True)
    )
    response = await request(app, "/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_is_503_when_disconnected() -> None:
    app = create_health_app(
        SimpleNamespace(db=FakeDB(True), switch=FakeSwitch(False), schema_ready=True)
    )
    response = await request(app, "/health/ready")
    assert response.status_code == 503
    assert response.json()["switch"] == "disconnected"


@pytest.mark.asyncio
async def test_readiness_is_503_when_schema_is_pending() -> None:
    app = create_health_app(
        SimpleNamespace(db=FakeDB(True), switch=FakeSwitch(True), schema_ready=False)
    )
    response = await request(app, "/health/ready")
    assert response.status_code == 503
    assert response.json()["schema"] == "pending"


@pytest.mark.asyncio
async def test_readiness_does_not_expose_private_ids() -> None:
    app = create_health_app(
        SimpleNamespace(db=FakeDB(True), switch=FakeSwitch(True), schema_ready=True)
    )
    response = await request(app, "/health/ready")
    text = response.text
    assert "room-1" not in text
    assert "@owner:test" not in text
    assert "agent-1" not in text
