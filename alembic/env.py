"""
Alembic migration environment for the tars service.

Async-aware (asyncpg + SQLAlchemy 2.x).
Reads DATABASE_URL from app.core.config.Settings so .env is the single
source of truth — no sqlalchemy.url in alembic.ini.

Import all ORM models below the Base import so that
Base.metadata knows about them when autogenerating migrations.
"""

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# app imports — must be resolvable from the project root
# ---------------------------------------------------------------------------
from app.core.config import settings
from app.db.postgres import Base

# noqa: F401 — side-effect imports that populate Base.metadata
import app.db.models  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
alembic_config = context.config

if alembic_config.config_file_name:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

logger = logging.getLogger("alembic.env")


# ---------------------------------------------------------------------------
# Offline mode — generates SQL without a live DB connection
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — runs migrations against a live DB
# ---------------------------------------------------------------------------


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
