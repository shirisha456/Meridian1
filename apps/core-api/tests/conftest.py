import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _test_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def sqlite_session():
    """A real (in-memory) async DB session — used to simulate a healthy
    database dependency without requiring Postgres for unit-level tests.
    Integration tests against real Postgres are added once there's a
    schema worth migrating (Phase 2 onward)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


class BrokenSession:
    """Stands in for a database that's unreachable — used to test the
    degraded-but-not-crashed path of /ready and /health."""

    async def execute(self, *args, **kwargs):
        raise ConnectionRefusedError("database unreachable")


async def broken_db_session():
    yield BrokenSession()
