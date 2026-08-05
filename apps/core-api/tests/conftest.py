from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.categories.models import Category
from app.core.config import get_settings
from app.core.db import Base, get_db
from app.core.redis import get_redis
from app.main import create_app

# Mirrors the fixed taxonomy seeded by the Phase 3 migration
# (alembic/versions/..._add_categories_accounts_and_transactions.py).
# The test DB is built via Base.metadata.create_all, not Alembic, so that
# migration's seed data has to be replicated here for tests that rely on
# GET /api/v1/categories returning something.
SEED_CATEGORY_NAMES = [
    "Income",
    "Housing",
    "Transportation",
    "Food & Dining",
    "Shopping",
    "Entertainment",
    "Health",
    "Bills & Utilities",
    "Savings & Investments",
    "Transfer",
    "Other",
]


@pytest.fixture(autouse=True)
def _test_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    # A real (test-only) Fernet key so institutions endpoints don't hit
    # EncryptionNotConfigured by default; test_encryption.py separately
    # covers the unset-key path directly against Settings.
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
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

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(Category(name=name) for name in SEED_CATEGORY_NAMES)
        await session.commit()

    yield engine
    await engine.dispose()


class BrokenRedis:
    """Stands in for an unreachable Redis — used to prove Redis-backed
    features fail open rather than erroring (ADR-0002). Implements every
    method app/core/cache.py calls, each raising the same RedisError a
    real client raises on a connection failure (not AttributeError,
    which would test a scenario that can't happen against a real Redis)."""

    async def get(self, *args, **kwargs):
        raise RedisError("redis unreachable")

    async def set(self, *args, **kwargs):
        raise RedisError("redis unreachable")

    async def delete(self, *args, **kwargs):
        raise RedisError("redis unreachable")

    async def incr(self, *args, **kwargs):
        raise RedisError("redis unreachable")

    async def expire(self, *args, **kwargs):
        raise RedisError("redis unreachable")

    def scan_iter(self, *args, **kwargs):
        async def _raise() -> AsyncGenerator[str, None]:
            raise RedisError("redis unreachable")
            yield ""  # pragma: no cover - unreachable, makes this an async generator

        return _raise()


async def broken_redis():
    yield BrokenRedis()


@pytest.fixture
async def authed_client(app, db_engine):
    """An HTTP client wired to a real (schema-backed) database and a
    real-protocol in-memory Redis (fakeredis) — for exercising routes
    that actually read/write, like everything under /api/v1."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with session_factory() as session:
            yield session

    fake_redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get_redis():
        yield fake_redis_client

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = _get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await fake_redis_client.aclose()


@pytest.fixture
async def auth_headers(authed_client):
    """Registers a default user and returns Bearer headers for it — for
    tests that need *a* logged-in user but the identity itself isn't the
    point (accounts, transactions, categories)."""
    response = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}
