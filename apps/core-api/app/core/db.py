from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


engine: AsyncEngine = create_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def database_is_ready(session: AsyncSession) -> bool:
    """Cheap connectivity check used by the readiness/health endpoints.

    A dedicated function (rather than an inline query in the router) so
    tests can override `get_db` with a stub session that raises here to
    simulate a database outage without needing a real Postgres down.
    """
    await session.execute(text("SELECT 1"))
    return True
