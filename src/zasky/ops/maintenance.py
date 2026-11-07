"""Local-only maintenance CLI: migrations, status, backup, restore, prune."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from zasky.ops.backup import (
    backup_database,
    prune_backups,
    restore_database,
)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _database_url(env_file: str | None, override: str | None) -> str:
    if override:
        return override
    if env_file:
        values = _read_env_file(Path(env_file))
        if "DATABASE_URL" in values:
            return values["DATABASE_URL"]
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/zasky.db")


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    os.environ["DATABASE_URL"] = database_url
    return config


def head_revision() -> str | None:
    config = Config("alembic.ini")
    try:
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception:
        return None


def current_revision(database_url: str) -> str | None:
    from zasky.storage.database import Database

    async def read() -> str | None:
        db = Database(database_url)
        try:
            return await db.get_schema_revision()
        finally:
            await db.close(close_connections=False)

    return asyncio.run(read())


def _cmd_migrate(args: argparse.Namespace) -> int:
    url = _database_url(args.env_file, args.database_url)
    command.upgrade(_alembic_config(url), "head")
    print(f"migrated: {current_revision(url)}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    url = _database_url(args.env_file, args.database_url)
    current = current_revision(url)
    head = head_revision()
    print(f"database: {current or 'uninitialized'}")
    print(f"head:     {head or 'unavailable'}")
    return 0 if current == head and head is not None else 1


def _cmd_backup(args: argparse.Namespace) -> int:
    url = _database_url(args.env_file, args.database_url)
    result = backup_database(url, Path(args.dest))
    print(f"backup:   {result.path}")
    print(f"integrity: {result.integrity}")
    print(f"sha256:   {result.sha256}")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    result = restore_database(
        Path(args.backup), Path(args.target), force=args.force
    )
    print(f"restored: {result.path}")
    print(f"integrity: {result.integrity}")
    print(f"foreign_key_violations: {result.foreign_key_violations}")
    print(f"tables:   {result.tables}")
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    removed = prune_backups(
        Path(args.dest), keep_daily=args.keep_daily, keep_weekly=args.keep_weekly
    )
    print(f"removed:  {len(removed)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Zasky local maintenance")
    parser.add_argument("--env-file", default=os.getenv("ZASKY_ENV_FILE"))
    parser.add_argument("--database-url", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="Apply Alembic migrations to head")

    sub.add_parser("status", help="Show current and head schema revisions")

    backup = sub.add_parser("backup", help="Create a consistent SQLite backup")
    backup.add_argument("--dest", default="data/backups")

    restore = sub.add_parser("restore", help="Restore a backup into a target path")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--target", required=True)
    restore.add_argument("--force", action="store_true")

    prune = sub.add_parser("prune", help="Prune old local backups")
    prune.add_argument("--dest", default="data/backups")
    prune.add_argument("--keep-daily", type=int, default=7)
    prune.add_argument("--keep-weekly", type=int, default=4)

    args = parser.parse_args()
    handlers = {
        "migrate": _cmd_migrate,
        "status": _cmd_status,
        "backup": _cmd_backup,
        "restore": _cmd_restore,
        "prune": _cmd_prune,
    }
    try:
        raise SystemExit(handlers[args.command](args))
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
