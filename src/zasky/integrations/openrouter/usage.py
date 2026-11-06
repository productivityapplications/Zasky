"""Simplified hard cost/request guard for the OpenRouter adapter.

No reservation ledger in the hackathon build: each request is checked against
the daily request cap and month-to-date spend, then recorded after the response.
Unknown usage is charged at the configured upper bound.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from zasky.config import Settings
from zasky.domain.errors import DomainError
from zasky.integrations.openrouter.client import LLMResponse
from zasky.storage.database import Database
from zasky.storage.models import ModelUsageRecord


class CostGuard:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._db = database
        self._settings = settings

    @property
    def monthly_cap_microusd(self) -> int:
        return int(round(self._settings.max_llm_spend_usd_month * 1_000_000))

    def estimate_microusd(self, input_tokens: int, output_tokens: int) -> int:
        return int(
            round(
                input_tokens * self._settings.openai_input_usd_per_1m
                + output_tokens * self._settings.openai_output_usd_per_1m
            )
        )

    async def check(self) -> None:
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        async with self._db.locked_session() as session:
            today_count = await session.scalar(
                select(func.count())
                .select_from(ModelUsageRecord)
                .where(ModelUsageRecord.occurred_at >= day_start)
            )
            month_spend = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(ModelUsageRecord.actual_cost_microusd), 0
                    )
                ).where(ModelUsageRecord.occurred_at >= month_start)
            )
        if int(today_count or 0) >= self._settings.max_llm_requests_per_day:
            raise DomainError(
                "RATE_LIMITED",
                "The daily model request limit has been reached. No request was sent.",
            )
        worst_case = self.estimate_microusd(
            self._settings.openai_max_input_tokens,
            self._settings.openai_max_output_tokens,
        )
        if int(month_spend or 0) + worst_case > self.monthly_cap_microusd:
            raise DomainError(
                "BUDGET_EXCEEDED",
                "The monthly model budget would be exceeded. No request was sent.",
            )

    async def record(
        self,
        response: LLMResponse,
        *,
        correlation_id: str,
        status: str = "succeeded",
    ) -> None:
        input_tokens = response.prompt_tokens
        output_tokens = response.completion_tokens
        if not response.usage_known or input_tokens == 0:
            input_tokens = self._settings.openai_max_input_tokens
        if not response.usage_known or output_tokens == 0:
            output_tokens = self._settings.openai_max_output_tokens
        actual = self.estimate_microusd(input_tokens, output_tokens)
        await self._store(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_microusd=actual,
            status=status if response.usage_known else "unknown",
            provider_request_id=response.provider_request_id,
            correlation_id=correlation_id,
        )

    async def record_failure(self, *, correlation_id: str) -> None:
        await self._store(
            input_tokens=0,
            output_tokens=0,
            actual_cost_microusd=0,
            status="failed",
            provider_request_id=None,
            correlation_id=correlation_id,
        )

    async def _store(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_microusd: int,
        status: str,
        provider_request_id: str | None,
        correlation_id: str,
    ) -> None:
        async with self._db.locked_session() as session:
            session.add(
                ModelUsageRecord(
                    id=str(uuid4()),
                    provider="openrouter",
                    provider_request_id=provider_request_id,
                    model=self._settings.openai_model,
                    pricing_version=self._settings.openai_price_effective_date,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    reserved_cost_microusd=0,
                    actual_cost_microusd=actual_cost_microusd,
                    status=status,
                    correlation_id=correlation_id,
                )
            )
            try:
                await session.commit()
            except Exception:
                await session.rollback()
