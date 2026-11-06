from __future__ import annotations

import asyncio
import sqlite3

import pytest

from zasky.ops.backup import (
    backup_database,
    prune_backups,
    restore_database,
)
from zasky.storage.database import Database
from zasky.storage.models import YearGoal


@pytest.mark.asyncio
async def test_online_backup_and_restore_proves_rows(tmp_path) -> None:
    db_path = tmp_path / "zasky.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    db = Database(db_url)
    await db.init()
    try:
        async with db.locked_session() as session:
            session.add(
                YearGoal(
                    id="goal-1",
                    year=2027,
                    title="Ship a working personal plan",
                    normalized_title="ship a working personal plan",
                    evidence_of_done="A dated review note and a passing demo",
                    status="active",
                )
            )
            await session.commit()

        result = backup_database(db_url, tmp_path / "backups")
        assert result.integrity == "ok"
        assert result.path.is_file()
        assert result.checksum_path.is_file()

        async with db.locked_session() as session:
            await session.execute(
                YearGoal.__table__.delete().where(YearGoal.id == "goal-1")
            )
            await session.commit()

        restored = tmp_path / "restored.db"
        checked = restore_database(result.path, restored)
        assert checked.integrity == "ok"
        assert checked.foreign_key_violations == 0

        connection = sqlite3.connect(restored)
        try:
            count = connection.execute("SELECT count(*) FROM year_goals").fetchone()
            assert count is not None and count[0] == 1
        finally:
            connection.close()
    finally:
        await db.close()
        await asyncio.sleep(0.2)


def test_restore_refuses_existing_target_without_force(tmp_path) -> None:
    backup = tmp_path / "backup.db"
    source = sqlite3.connect(backup)
    source.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)")
    source.execute("INSERT INTO t (value) VALUES ('kept')")
    source.commit()
    source.close()

    target = tmp_path / "target.db"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        restore_database(backup, target)
    assert target.read_bytes() == b"existing"


def test_prune_keeps_recent_daily_copies(tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    paths = []
    for index in range(10):
        path = backup_dir / f"zasky-2026110{index}T000000Z.db"
        path.write_bytes(b"x")
        paths.append(path)
    removed = prune_backups(backup_dir, keep_daily=3, keep_weekly=1)
    assert len(removed) >= 1
    assert len(list(backup_dir.glob("zasky-*.db"))) <= 4
