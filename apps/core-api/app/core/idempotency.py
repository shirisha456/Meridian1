import json
import logging
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


def _cache_key(user_id: UUID, idempotency_key: str) -> str:
    # Scoped per-user rather than global — two different users choosing
    # the same client-generated key (however unlikely) must never let one
    # user's cached response leak into another's.
    return f"idempotency:{user_id}:{idempotency_key}"


async def get_cached_response(redis_client: redis.Redis, user_id: UUID, key: str) -> dict | None:
    """Fails open: a Redis outage is treated as a cache miss, not an
    error. Idempotency here is a safety net against accidental client
    retries creating duplicate manual transactions — a real but
    recoverable annoyance in this domain, not a reason to make the whole
    write path depend on Redis being up. See ADR-0002."""
    try:
        cached = await redis_client.get(_cache_key(user_id, key))
    except RedisError:
        logger.warning("Idempotency cache read failed; proceeding as a cache miss.", exc_info=True)
        return None
    return json.loads(cached) if cached else None


async def cache_response(redis_client: redis.Redis, user_id: UUID, key: str, response: dict) -> None:
    try:
        await redis_client.set(
            _cache_key(user_id, key),
            json.dumps(response, default=str),
            ex=IDEMPOTENCY_TTL_SECONDS,
        )
    except RedisError:
        logger.warning("Idempotency cache write failed; response was not cached.", exc_info=True)
