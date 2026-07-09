
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import app.db.models  # noqa: F401 — side-effect import: registers all ORM models with Base.metadata
from app.core.config import settings
from app.db.postgres import Base

# ---------------------------------------------------------------------------
# Test DB URL resolution
# ---------------------------------------------------------------------------


def _test_database_url() -> str:
    if explicit := os.environ.get("TEST_DATABASE_URL"):
        return explicit
    # Derive: postgresql+asyncpg://user:pw@host:port/tars  →  .../tars_test
    return settings.DATABASE_URL + "_test"


TEST_DATABASE_URL = _test_database_url()


# ---------------------------------------------------------------------------
# Session-scoped engine — schema created once per pytest run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        # pg_trgm is required for the GIN trigram indexes defined on packet and
        # agreement_version.  Alembic enables it in the migration; we do the
        # same here since tests bypass Alembic entirely.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped session — rolled back after every test
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:  # type: ignore[misc]
    async with test_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
