import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import Base, get_db
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


@pytest.fixture
async def db_engine():
    """A schema-backed in-memory SQLite database — one shared connection
    per test (StaticPool), so every session in a test sees the same data
    instead of each getting its own empty in-memory DB."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def authed_client(app, db_engine):
    """An HTTP client wired to a real (schema-backed) database — for
    exercising routes that actually read/write, like everything under
    /api/v1/auth."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
