from __future__ import annotations

import pytest

from tests.fixtures.identities import OWNER_ID, ROOM_ID
from zasky.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        log_level="DEBUG",
        database_url="sqlite+aiosqlite:///:memory:",
        switch_base_url="http://switch.test",
        switch_agent_id="agent-1",
        switch_agent_api_key="test-api-key",
        switch_connection_id="conn-1",
        switch_room_id=ROOM_ID,
        owner_switch_participant_id=OWNER_ID,
        health_bind_port=8099,
        switch_reconnect_min_seconds=0.05,
        switch_reconnect_max_seconds=0.2,
    )
