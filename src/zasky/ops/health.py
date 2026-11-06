"""Private liveness and readiness endpoints.

These endpoints are bound to localhost by default. They must not expose owner
IDs, room IDs, secrets, task text or schedule data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Response

if TYPE_CHECKING:
    from zasky.app import ZaskyApp


def create_health_app(app: ZaskyApp) -> FastAPI:
    health = FastAPI(
        title="Zasky private health",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @health.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @health.get("/health/ready")
    async def ready(response: Response) -> dict[str, str]:
        database_ok = await app.db.healthcheck()
        switch_ok = app.switch.is_ready
        schema_ok = app.schema_ready
        ready_now = database_ok and switch_ok and schema_ok
        if not ready_now:
            response.status_code = 503
        return {
            "status": "ready" if ready_now else "not_ready",
            "database": "ok" if database_ok else "unavailable",
            "switch": "connected" if switch_ok else "disconnected",
            "schema": "current" if schema_ok else "pending",
        }

    return health
