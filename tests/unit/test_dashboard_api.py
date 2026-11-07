from __future__ import annotations

import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio

from tests.fixtures.identities import OWNER_ID, ROOM_ID
from zasky.config import Settings
from zasky.domain.schemas import (
    AddCommitmentRequest,
    PlaceWeekRequest,
    PlaceWeekTask,
    PlanDayRequest,
    QueryRequest,
)
from zasky.domain.service import DomainService
from zasky.ops.dashboard_api import create_dashboard_app
from zasky.storage.database import Database
from zasky.storage.repositories import OwnerConfigRepository

AVAILABILITY = (
    '{"monday": [{"start": "09:00", "end": "17:00"}], '
    '"tuesday": [{"start": "09:00", "end": "17:00"}], '
    '"wednesday": [{"start": "09:00", "end": "17:00"}], '
    '"thursday": [{"start": "09:00", "end": "17:00"}], '
    '"friday": [{"start": "09:00", "end": "17:00"}], '
    '"saturday": [{"start": "09:00", "end": "17:00"}], '
    '"sunday": [{"start": "09:00", "end": "17:00"}]}'
)
TOKEN = "dashboard-test-token"  # noqa: S105 - synthetic test credential


async def approve(service: DomainService, result: dict) -> dict:
    return await service.resolve_proposal(
        action="approve",
        code=result["proposal"],
        actor_id=OWNER_ID,
        room_id=ROOM_ID,
    )


@pytest_asyncio.fixture
async def dashboard_env(tmp_path, settings: Settings):
    configured = settings.model_copy(
        update={
            "database_url": f"sqlite+aiosqlite:///{tmp_path / 'dashboard.db'}",
            "dashboard_api_key": TOKEN,
            "dashboard_cors_origins": "*",
            "timezone": "Africa/Lagos",
            "weekly_availability_json": AVAILABILITY,
        }
    )
    db = Database(configured.database_url)
    await db.init()
    await OwnerConfigRepository(db).ensure_seeded(configured)
    domain = DomainService(db, configured)
    try:
        goal = await domain.propose_record(
            AddCommitmentRequest(
                operation="create",
                entry_type="year_goal",
                title="Ship the dashboard",
                year=2026,
                evidence_of_done="A reviewed dashboard and a passing task completion.",
            )
        )
        await approve(domain, goal)
        goals = await domain.query(QueryRequest(state="goals", horizon="2026"))
        commitment = await domain.propose_record(
            AddCommitmentRequest(
                operation="create",
                entry_type="month_commitment",
                title="Ship the dashboard safely",
                year=2026,
                month=11,
                goal_id=goals["goals"][0]["id"],
                est_min=120,
                deadline_local_date=date(2026, 11, 30),
                consequence="Judges cannot see the plan.",
                priority="high",
            )
        )
        await approve(domain, commitment)
        commitments = await domain.query(
            QueryRequest(state="month", horizon="2026-11")
        )
        week = await domain.propose_week(
            PlaceWeekRequest(
                week_start=date(2026, 11, 2),
                tasks=[
                    PlaceWeekTask(
                        commitment_id=commitments["commitments"][0]["id"],
                        task_title="Polish the dashboard",
                        est_min=45,
                        scheduled_date=date(2026, 11, 6),
                    )
                ],
            )
        )
        await approve(domain, week)
        day = await domain.propose_day(
            PlanDayRequest(date=date(2026, 11, 6), battery="high")
        )
        await approve(domain, day)
        fixed = await domain.propose_record(
            AddCommitmentRequest(
                operation="create",
                entry_type="fixed_event",
                title="Synthetic review",
                starts_at=datetime(
                    2026, 11, 6, 18, 0, tzinfo=ZoneInfo("Africa/Lagos")
                ),
                ends_at=datetime(
                    2026, 11, 6, 19, 0, tzinfo=ZoneInfo("Africa/Lagos")
                ),
            )
        )
        await approve(domain, fixed)
        api = create_dashboard_app(
            SimpleNamespace(settings=configured, db=db, domain=domain)  # type: ignore[arg-type]
        )
        yield api, db, domain
    finally:
        await db.close(close_connections=False)
        await asyncio.sleep(0.2)


def client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://dashboard.test",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


@pytest.mark.asyncio
async def test_dashboard_requires_bearer_token(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api),
        base_url="http://dashboard.test",
    ) as anonymous:
        response = await anonymous.get("/api/dashboard/today")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        wrong = await anonymous.get(
            "/api/dashboard/today",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert wrong.status_code == 401
        assert "wrong-token" not in wrong.text


@pytest.mark.asyncio
async def test_today_returns_must_should_and_fixed_events(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/today?date=2026-11-06")
        assert response.status_code == 200
        payload = response.json()
        assert payload["has_plan"] is True
        assert payload["timezone"] == "Africa/Lagos"
        assert payload["battery"] == "high"
        assert payload["must"][0]["title"] == "Polish the dashboard"
        assert payload["must"][0]["planned_start_display"]
        assert payload["must"][0]["planned_end_display"]
        assert payload["should"] == []
        assert payload["latest_wake_display"]
        assert payload["fixed_events"][0]["title"] == "Synthetic review"


@pytest.mark.asyncio
async def test_today_without_a_plan_is_explicit(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/today?date=2026-11-07")
        assert response.status_code == 200
        payload = response.json()
        assert payload["has_plan"] is False
        assert payload["must"] == []
        assert payload["should"] == []


@pytest.mark.asyncio
async def test_tasks_can_be_listed_and_completed(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with client(api) as http:
        listing = await http.get("/api/dashboard/tasks")
        assert listing.status_code == 200
        body = listing.json()
        assert body["counts"]["active"] == 1
        task = body["tasks"][0]
        assert task["title"] == "Polish the dashboard"
        assert task["commitment_title"] == "Ship the dashboard safely"

        completed = await http.post(
            f"/api/dashboard/tasks/{task['id']}/complete",
            json={"actual_min": 40},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

        after = await http.get("/api/dashboard/tasks")
        assert after.json()["counts"]["completed"] == 1
        assert after.json()["tasks"][0]["actual_min"] == 40
        today = await http.get("/api/dashboard/today?date=2026-11-06")
        assert today.json()["must"][0]["outcome"] == "completed"


@pytest.mark.asyncio
async def test_unknown_task_completion_returns_404(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with client(api) as http:
        response = await http.post("/api/dashboard/tasks/missing/complete")
        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tasks_rejects_unknown_status(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/tasks?status=exploded")
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_reconciliation_history_is_available(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/reconciliations")
        assert response.status_code == 200
        assert response.json()["reconciliations"] == []


@pytest.mark.asyncio
async def test_cors_preflight_allows_vercel_browser(dashboard_env) -> None:
    api, _db, _domain = dashboard_env
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api),
        base_url="http://dashboard.test",
    ) as anonymous:
        response = await anonymous.options(
            "/api/dashboard/today",
            headers={
                "Origin": "https://example.vercel.app",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
