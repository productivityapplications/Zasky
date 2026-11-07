from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from zasky.config import normalize_database_url
from zasky.storage.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

database_url = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/zasky.db")
)
config.set_main_option("sqlalchemy.url", database_url)


def configure_context(connection=None) -> None:
    is_sqlite = (
        connection.dialect.name == "sqlite"
        if connection is not None
        else database_url.startswith("sqlite")
    )
    context.configure(
        connection=connection,
        url=None if connection is not None else database_url,
        target_metadata=target_metadata,
        literal_binds=connection is None,
        dialect_opts={"paramstyle": "named"} if connection is None else None,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=is_sqlite,
        include_schemas=False,
    )


def run_migrations_offline() -> None:
    configure_context()
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    configure_context(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
