from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.integrations.openrouter.client import LLMResponse
from zasky.integrations.openrouter.usage import CostGuard
from zasky.storage.database import Database


def llm_response(request_id: str = "req-1") -> LLMResponse:
    return LLMResponse(
        content="ok",
        prompt_tokens=1000,
        completion_tokens=500,
        provider_request_id=request_id,
        usage_known=True,
    )


@pytest.mark.asyncio
async def test_daily_request_cap_blocks_before_call(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'guard.db'}")
    await db.init()
    try:
        limited = settings.model_copy(
            update={
                "openai_api_key": SecretStr("test"),
                "max_llm_requests_per_day": 1,
            }
        )
        guard = CostGuard(db, limited)
        await guard.check()
        await guard.record(llm_response("req-1"), correlation_id="c1")
        with pytest.raises(DomainError) as exc:
            await guard.check()
        assert exc.value.code == "RATE_LIMITED"
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_monthly_budget_blocks_before_call(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'guard.db'}")
    await db.init()
    try:
        tight = settings.model_copy(
            update={
                "openai_api_key": SecretStr("test"),
                "max_llm_spend_usd_month": 0.001,
            }
        )
        guard = CostGuard(db, tight)
        with pytest.raises(DomainError) as exc:
            await guard.check()
        assert exc.value.code == "BUDGET_EXCEEDED"
    finally:
        await db.close()
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_pricing_matches_configured_rates(tmp_path, settings: Settings) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'guard.db'}")
    await db.init()
    try:
        priced = settings.model_copy(
            update={
                "openai_api_key": SecretStr("test"),
                "openai_input_usd_per_1m": 0.15,
                "openai_output_usd_per_1m": 0.60,
            }
        )
        guard = CostGuard(db, priced)
        # 1000 * 0.15 + 500 * 0.60 = 450 micro-USD.
        assert guard.estimate_microusd(1000, 500) == 450
    finally:
        await db.close()
        await asyncio.sleep(0.2)
