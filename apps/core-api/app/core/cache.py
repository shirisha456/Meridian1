import json
import logging
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


async def cache_get_json(redis_client: redis.Redis, key: str) -> Any | None:
    """Fails open on a Redis error — see ADR-0002. Every cache-shaped
    Redis use in this app (idempotency keys, response caching) goes
    through this pair of functions so that failure mode only has to be
    implemented, and trusted, once."""
    try:
        cached = await redis_client.get(key)
    except RedisError:
        logger.warning("Cache read failed for key %s; treating as a miss.", key, exc_info=True)
        return None
    return json.loads(cached) if cached else None


async def cache_set_json(redis_client: redis.Redis, key: str, value: Any, *, ttl_seconds: int) -> None:
    try:
        await redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except RedisError:
        logger.warning("Cache write failed for key %s; response was not cached.", key, exc_info=True)


async def cache_delete_prefix(redis_client: redis.Redis, prefix: str) -> None:
    """SCAN + delete rather than KEYS — non-blocking on the Redis server
    even with a large keyspace. Acceptable at this app's scale; would be
    replaced by tagged cache keys or a pub/sub invalidation signal well
    before the SCAN cursor itself became the bottleneck."""
    try:
        async for key in redis_client.scan_iter(match=f"{prefix}*"):
            await redis_client.delete(key)
    except RedisError:
        logger.warning("Cache invalidation failed for prefix %s.", prefix, exc_info=True)
