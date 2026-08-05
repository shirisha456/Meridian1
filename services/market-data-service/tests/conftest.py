import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import metadata


@pytest.fixture
async def db_engine():
    """A minimal schema — just the columns this service's own Table()
    declarations reference — built fresh per test. Same "minimal column
    subset" contract as services/enrichment-service/tests/conftest.py
    (ADR-0007), exercised for real rather than mocked."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)
