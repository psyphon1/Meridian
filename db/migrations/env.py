"""Alembic environment — async SQLAlchemy engine.

The database URL is resolved in this order:

1. ``config.attributes["database_url"]`` — set programmatically (tests, tooling).
2. the ``DATABASE_URL`` environment variable — enough for CLI use, no other
   application settings required.
3. ``packages.config.settings.get_settings().database_url`` — full application
   settings (also reads ``.env``).

CLI usage (from the repository root)::

    alembic -c db/migrations/alembic.ini upgrade head
"""

import asyncio
import os
from logging.config import fileConfig

import packages.models.audit
import packages.models.identity
import packages.models.repository
import packages.models.review  # noqa: F401
from alembic import context
from packages.models.base import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
    if url:
        return str(url)
    from packages.config.settings import get_settings

    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(run_migrations_online())
    else:
        # Invoked from inside a running event loop (e.g. an async test calling
        # command.upgrade): asyncio.run() would raise, so run on a worker thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool_:
            pool_.submit(asyncio.run, run_migrations_online()).result()
