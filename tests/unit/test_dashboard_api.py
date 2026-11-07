from __future__ import annotations

import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr

from tests.fixtures.identities import OWNER_ID, ROOM_ID
from zasky.agent.execution import ExecutionSubAgentError
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


class FakePublisher:
    def __init__(self) -> None:
        self.delivered = True
        self.calls: list[dict[str, Any]] = []
        self.delegate_calls: list[dict[str, Any]] = []
        self.delegate_error: Exception | None = None
        self.delegate_result = {
            "task_id": "task-1",
            "title": "Polish the dashboard",
            "output": "Draft deliverable from the sub-agent.",
            "model": "openai/gpt-4o-mini",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "discord_delivered": True,
        }

    async def publish_execution_result(
        self, *, title: str, body: str, task_id: str | None = None
    ) -> bool:
        self.calls.append({"title": title, "body": body, "task_id": task_id})
        return self.delivered

    async def delegate_task(
        self, task_id: str, instruction: str | None = None
    ) -> dict[str, Any]:
        self.delegate_calls.append(
            {"task_id": task_id, "instruction": instruction}
        )
        if self.delegate_error is not None:
            raise self.delegate_error
        return {**self.delegate_result, "task_id": task_id}


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
            "calendar_feed_token": SecretStr("calendar-test-token"),
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
        publisher = FakePublisher()
        fake_app = SimpleNamespace(
            settings=configured,
            db=db,
            domain=domain,
            publish_execution_result=publisher.publish_execution_result,
            delegate_task=publisher.delegate_task,
        )
        api = create_dashboard_app(fake_app)  # type: ignore[arg-type]
        yield api, db, domain, publisher
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
    api, _db, _domain, _publisher = dashboard_env
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
    api, _db, _domain, _publisher = dashboard_env
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
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/today?date=2026-11-07")
        assert response.status_code == 200
        payload = response.json()
        assert payload["has_plan"] is False
        assert payload["must"] == []
        assert payload["should"] == []


@pytest.mark.asyncio
async def test_tasks_can_be_listed_and_completed(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
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
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        response = await http.post("/api/dashboard/tasks/missing/complete")
        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tasks_rejects_unknown_status(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/tasks?status=exploded")
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_reconciliation_history_is_available(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        response = await http.get("/api/dashboard/reconciliations")
        assert response.status_code == 200
        assert response.json()["reconciliations"] == []


@pytest.mark.asyncio
async def test_cors_preflight_allows_vercel_browser(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
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


@pytest.mark.asyncio
async def test_execution_result_routes_to_ai_workspace(dashboard_env) -> None:
    api, _db, _domain, publisher = dashboard_env
    async with client(api) as http:
        response = await http.post(
            "/api/internal/execution-results",
            json={
                "title": "Draft complete",
                "body": "The execution sub-agent produced a first draft.",
                "task_id": "task-1",
            },
        )
        assert response.status_code == 200
        assert response.json()["channel"] == "ai-workspace"
        assert publisher.calls == [
            {
                "title": "Draft complete",
                "body": "The execution sub-agent produced a first draft.",
                "task_id": "task-1",
            }
        ]


@pytest.mark.asyncio
async def test_execution_result_requires_configuration(dashboard_env) -> None:
    api, _db, _domain, publisher = dashboard_env
    publisher.delivered = False
    async with client(api) as http:
        response = await http.post(
            "/api/internal/execution-results",
            json={"title": "Draft", "body": "Body"},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_goal_and_commitment_from_dashboard(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        goal_response = await http.post(
            "/api/dashboard/goals",
            json={
                "title": "Launch the beta",
                "year": 2027,
                "evidence_of_done": "A reviewed launch checklist.",
            },
        )
        assert goal_response.status_code == 200
        goal = goal_response.json()["goal"]
        assert goal["status"] == "active"

        goals = await http.get("/api/dashboard/goals")
        assert any(row["title"] == "Launch the beta" for row in goals.json()["goals"])

        commitment_response = await http.post(
            "/api/dashboard/commitments",
            json={
                "title": "Ship the beta",
                "year": 2027,
                "month": 1,
                "goal_id": goal["id"],
                "est_min": 300,
                "deadline_local_date": "2027-01-31",
                "consequence": "The beta slips.",
                "priority": "high",
            },
        )
        assert commitment_response.status_code == 200
        commitment = commitment_response.json()["commitment"]
        assert commitment["goal_id"] == goal["id"]

        commitments = await http.get("/api/dashboard/commitments")
        row = next(
            item
            for item in commitments.json()["commitments"]
            if item["id"] == commitment["id"]
        )
        assert row["goal_title"] == "Launch the beta"


@pytest.mark.asyncio
async def test_create_task_from_dashboard_uses_week_pool(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        commitments = await http.get("/api/dashboard/commitments")
        commitment_id = next(
            item["id"]
            for item in commitments.json()["commitments"]
            if item["title"] == "Ship the dashboard safely"
        )
        linked = await http.post(
            "/api/dashboard/tasks",
            json={
                "title": "Add a dashboard task",
                "est_min": 20,
                "scheduled_date": "2026-11-06",
                "commitment_id": commitment_id,
            },
        )
        assert linked.status_code == 200
        assert linked.json()["task"]["ad_hoc"] is False

        ad_hoc = await http.post(
            "/api/dashboard/tasks",
            json={
                "title": "Dashboard ad hoc task",
                "est_min": 15,
                "scheduled_date": "2026-11-06",
            },
        )
        assert ad_hoc.status_code == 200
        assert ad_hoc.json()["task"]["ad_hoc"] is True

        listing = await http.get("/api/dashboard/tasks")
        titles = {task["title"] for task in listing.json()["tasks"]}
        assert "Add a dashboard task" in titles
        assert "Dashboard ad hoc task" in titles


@pytest.mark.asyncio
async def test_delegate_returns_execution_output(dashboard_env) -> None:
    api, _db, _domain, publisher = dashboard_env
    async with client(api) as http:
        listing = await http.get("/api/dashboard/tasks")
        task = next(
            item for item in listing.json()["tasks"] if item["status"] == "active"
        )
        response = await http.post(
            f"/api/dashboard/delegate/{task['id']}",
            json={"instruction": "Make it concise."},
        )
        assert response.status_code == 200
        assert response.json()["output"].startswith("Draft deliverable")
        assert publisher.delegate_calls == [
            {"task_id": task["id"], "instruction": "Make it concise."}
        ]


@pytest.mark.asyncio
async def test_delegate_conflict_is_reported(dashboard_env) -> None:
    api, _db, _domain, publisher = dashboard_env
    publisher.delegate_error = ExecutionSubAgentError(
        "CONFLICT", "A completed task cannot be delegated."
    )
    async with client(api) as http:
        response = await http.post("/api/dashboard/delegate/task-1")
        assert response.status_code == 409
        assert "cannot be delegated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_calendar_feed_accepts_feed_token_and_bearer(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api),
        base_url="http://dashboard.test",
    ) as anonymous:
        missing = await anonymous.get("/api/dashboard/calendar.ics")
        assert missing.status_code == 401
        wrong = await anonymous.get(
            "/api/dashboard/calendar.ics?token=wrong"
        )
        assert wrong.status_code == 401
        feed = await anonymous.get(
            "/api/dashboard/calendar.ics?token=calendar-test-token"
        )
        assert feed.status_code == 200
        assert feed.headers["content-type"].startswith("text/calendar")
        body = feed.text
        assert body.startswith("BEGIN:VCALENDAR")
        assert "SUMMARY:Polish the dashboard" in body
        assert "SUMMARY:Synthetic review" in body
        assert "BEGIN:VALARM" in body
        assert "TRIGGER:-PT5M" in body

    async with client(api) as http:
        bearer = await http.get("/api/dashboard/calendar.ics")
        assert bearer.status_code == 200
        assert "BEGIN:VCALENDAR" in bearer.text


@pytest.mark.asyncio
async def test_task_payloads_include_google_calendar_links(dashboard_env) -> None:
    api, _db, _domain, _publisher = dashboard_env
    async with client(api) as http:
        today = await http.get("/api/dashboard/today?date=2026-11-06")
        item = today.json()["must"][0]
        assert "calendar.google.com/calendar/render" in item["google_calendar_url"]
        assert "action=TEMPLATE" in item["google_calendar_url"]

        listing = await http.get("/api/dashboard/tasks")
        tasks = listing.json()["tasks"]
        assert tasks
        assert all(task["google_calendar_url"] for task in tasks)
