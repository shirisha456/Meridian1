from collections.abc import AsyncGenerator

import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _client


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    yield _get_client()
