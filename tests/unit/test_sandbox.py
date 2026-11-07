from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import httpx
import pytest
from pydantic import SecretStr

from zasky.config import Settings
from zasky.domain.schemas import QueryRequest
from zasky.ops.dashboard_api import create_dashboard_app
from zasky.ops.sandbox import build_sandbox_scope

AVAILABILITY = (
    '{"monday": [{"start": "09:00", "end": "21:00"}], '
    '"tuesday": [{"start": "09:00", "end": "21:00"}], '
    '"wednesday": [{"start": "09:00", "end": "21:00"}], '
    '"thursday": [{"start": "09:00", "end": "21:00"}], '
    '"friday": [{"start": "09:00", "end": "21:00"}], '
    '"saturday": [{"start": "09:00", "end": "21:00"}], '
    '"sunday": [{"start": "09:00", "end": "21:00"}]}'
)


@pytest.mark.asyncio
async def test_sandbox_scope_seeds_isolated_demo(tmp_path, settings: Settings) -> None:
    configured = settings.model_copy(
        update={
            "sandbox_database_url": (
                f"sqlite+aiosqlite:///{tmp_path / 'sandbox.db'}"
            ),
            "sandbox_switch_room_id": "sandbox-room",
            "weekly_availability_json": AVAILABILITY,
        }
    )
    scope = await build_sandbox_scope(configured)
    try:
        goals = await scope.domain.query(
            QueryRequest(
                state="goals",
                horizon=str(datetime.now(UTC).astimezone(ZoneInfo(configured.timezone)).year),
            )
        )
        assert len(goals["goals"]) == 1
        active = await scope.domain.query(
            QueryRequest(
                state="today",
                horizon=datetime.now(UTC)
                .astimezone(ZoneInfo(configured.timezone))
                .date()
                .isoformat(),
            )
        )
        assert len(active["items"]) >= 1
        week = await scope.domain.query(
            QueryRequest(
                state="week",
                horizon=(
                    datetime.now(UTC)
                    .astimezone(ZoneInfo(configured.timezone))
                    .date()
                    .replace(day=1)
                    .isoformat()
                ),
            )
        )
        assert week["week_start"]
        assert scope.owner_id == "@sandbox:judge"
        assert scope.room_id == "sandbox-room"
    finally:
        await scope.db.close(close_connections=False)
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_sandbox_dashboard_scope_is_isolated(tmp_path, settings: Settings) -> None:
    configured = settings.model_copy(
        update={
            "sandbox_database_url": (
                f"sqlite+aiosqlite:///{tmp_path / 'sandbox-dashboard.db'}"
            ),
            "sandbox_switch_room_id": "sandbox-room",
            "weekly_availability_json": AVAILABILITY,
            "dashboard_api_key": SecretStr("sandbox-token"),
        }
    )
    scope = await build_sandbox_scope(configured)
    api = create_dashboard_app(
        SimpleNamespace(settings=configured),  # type: ignore[arg-type]
        scope=SimpleNamespace(
            db=scope.db,
            domain=scope.domain,
            delegate_from_dashboard=lambda *a, **k: None,
            approve_execution=lambda *a, **k: None,
        ),
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api),
            base_url="http://sandbox.test",
            headers={"Authorization": "Bearer sandbox-token"},
        ) as http:
            listing = await http.get("/api/dashboard/tasks")
            assert listing.status_code == 200
            types = {
                task["execution_type"] for task in listing.json()["tasks"]
            }
            assert types == {"human", "ai"}
            created = await http.post(
                "/api/dashboard/tasks",
                json={
                    "title": "Write a judge follow-up email",
                    "est_min": 15,
                    "scheduled_date": (
                        datetime.now(UTC)
                        .astimezone(ZoneInfo(configured.timezone))
                        .date()
                        .isoformat()
                    ),
                    "execution_type": "ai",
                },
            )
            assert created.status_code == 200
            assert created.json()["task"]["execution_type"] == "ai"
    finally:
        await scope.db.close(close_connections=False)
        await asyncio.sleep(0.2)
