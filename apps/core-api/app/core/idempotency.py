from uuid import UUID

import redis.asyncio as redis

from app.core.cache import cache_get_json, cache_set_json

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


def _cache_key(user_id: UUID, idempotency_key: str) -> str:
    # Scoped per-user rather than global — two different users choosing
    # the same client-generated key (however unlikely) must never let one
    # user's cached response leak into another's.
    return f"idempotency:{user_id}:{idempotency_key}"


async def get_cached_response(redis_client: redis.Redis, user_id: UUID, key: str) -> dict | None:
    return await cache_get_json(redis_client, _cache_key(user_id, key))


async def cache_response(redis_client: redis.Redis, user_id: UUID, key: str, response: dict) -> None:
    await cache_set_json(redis_client, _cache_key(user_id, key), response, ttl_seconds=IDEMPOTENCY_TTL_SECONDS)
