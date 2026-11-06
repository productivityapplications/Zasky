from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_migration_upgrade_check_and_append_only_audit(tmp_path) -> None:
    database = tmp_path / "migrated.db"
    url = f"sqlite+aiosqlite:///{database}"

    upgraded = run_alembic(url, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr

    checked = run_alembic(url, "check")
    assert checked.returncode == 0, checked.stderr
    assert "No new upgrade operations detected" in checked.stdout

    connection = sqlite3.connect(database)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "alembic_version" in tables
        assert "owner_config" in tables
        assert "year_goals" in tables
        assert "week_tasks" in tables
        assert "day_plan_items" in tables
        assert "pending_proposals" in tables
        assert "audit_events" in tables
        assert "processed_switch_events" in tables

        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
        assert {"audit_events_no_update", "audit_events_no_delete"} <= triggers

        connection.execute(
            "INSERT INTO audit_events "
            "(id, actor_type, actor_id, action, entity_type, entity_id, "
            " summary_redacted, correlation_id, created_at) "
            "VALUES ('a1', 'system', NULL, 'test', NULL, NULL, 'safe', 'c1', "
            "        '2026-11-06T00:00:00Z')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE audit_events SET action='changed' WHERE id='a1'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM audit_events WHERE id='a1'")
    finally:
        connection.close()

    downgraded = run_alembic(url, "downgrade", "base")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database)
    try:
        remaining = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert remaining == {"alembic_version"}
    finally:
        connection.close()

    reupgraded = run_alembic(url, "upgrade", "head")
    assert reupgraded.returncode == 0, reupgraded.stderr
