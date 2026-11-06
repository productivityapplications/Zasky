"""Manual SQLite online backup and restore verification.

Encrypted backup automation is intentionally deferred for the hackathon demo.
This module still proves the important property: the database can be copied
safely while WAL is active and restored with integrity checks.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class BackupResult:
    path: Path
    checksum_path: Path
    sha256: str
    created_at: datetime
    integrity: str


@dataclass(frozen=True)
class RestoreResult:
    path: Path
    integrity: str
    foreign_key_violations: int
    tables: int


def database_path(database_url: str) -> Path:
    parsed = make_url(database_url)
    if parsed.database in (None, "", ":memory:"):
        raise ValueError("backup requires a file-backed SQLite database")
    return Path(parsed.database)


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


def backup_database(
    database_url: str,
    backup_dir: Path,
    *,
    now: datetime | None = None,
) -> BackupResult:
    """Create a consistent online copy and a SHA-256 sidecar."""
    source_path = database_path(database_url)
    if not source_path.is_file():
        raise FileNotFoundError(str(source_path))

    backup_dir.mkdir(parents=True, exist_ok=True)
    created = now or datetime.now(UTC)
    stamp = created.strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"zasky-{stamp}.db"
    if destination.exists():
        raise FileExistsError(str(destination))

    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(destination))
    try:
        source.backup(target)
        integrity_row = target.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "unknown"
        if integrity != "ok":
            raise RuntimeError(f"backup integrity check failed: {integrity}")
    finally:
        target.close()
        source.close()

    destination.chmod(0o600)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    checksum_path.write_text(
        f"{digest}  {destination.name}\ncreated_at={created.isoformat()}\n",
        encoding="utf-8",
    )
    checksum_path.chmod(0o600)
    return BackupResult(
        path=destination,
        checksum_path=checksum_path,
        sha256=digest,
        created_at=created,
        integrity=integrity,
    )


def restore_database(
    backup_path: Path,
    target_path: Path,
    *,
    force: bool = False,
) -> RestoreResult:
    """Restore into a target path after integrity and foreign-key checks."""
    if not backup_path.is_file():
        raise FileNotFoundError(str(backup_path))
    if target_path.exists():
        if not force:
            raise FileExistsError(
                f"{target_path} exists; pass force=True only after stopping the writer"
            )
        target_path.unlink()
        _remove_sqlite_sidecars(target_path)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
    target = sqlite3.connect(str(target_path))
    try:
        source.backup(target)
        integrity_row = target.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "unknown"
        violations = target.execute("PRAGMA foreign_key_check").fetchall()
        table_count = target.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        tables = int(table_count[0]) if table_count else 0
        if integrity != "ok":
            raise RuntimeError(f"restored database integrity check failed: {integrity}")
        if violations:
            raise RuntimeError(
                f"restored database has {len(violations)} foreign-key violation(s)"
            )
    finally:
        target.close()
        source.close()

    target_path.chmod(0o600)
    return RestoreResult(
        path=target_path,
        integrity=integrity,
        foreign_key_violations=len(violations),
        tables=tables,
    )


def prune_backups(
    backup_dir: Path,
    *,
    keep_daily: int = 7,
    keep_weekly: int = 4,
) -> list[Path]:
    """Keep recent daily copies and one copy per ISO week for recent weeks."""
    backups = sorted(
        backup_dir.glob("zasky-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    keep: set[Path] = set(backups[:keep_daily])
    seen_weeks: set[tuple[int, int]] = set()
    for path in backups:
        iso = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isocalendar()
        week = (iso.year, iso.week)
        if week not in seen_weeks:
            seen_weeks.add(week)
            keep.add(path)
        if len(seen_weeks) >= keep_weekly:
            break

    removed: list[Path] = []
    for path in backups:
        if path in keep:
            continue
        checksum = path.with_suffix(path.suffix + ".sha256")
        path.unlink(missing_ok=True)
        checksum.unlink(missing_ok=True)
        removed.append(path)
    return removed
