import logging

import redis.asyncio as redis
from fastapi import Depends, Request
from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.errors import TooManyRequestsError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window, per-client-IP request limiter for unauthenticated
    endpoints (login, register) — there's no user_id yet to scope by, and
    IP is the only signal available before authentication succeeds.

    Fails open on a Redis error (ADR-0002): a Redis outage degrades this
    to "no rate limiting" rather than locking every user out of login,
    which would turn a cache dependency into an availability dependency
    for the single most critical path in the app.

    A fixed window (INCR + EXPIRE on first hit) rather than a sliding
    window or token bucket — simpler, O(1) per request, and "up to twice
    the limit at a window boundary" is an acceptable imprecision for
    slowing down brute-force/credential-stuffing attempts, not a hard
    security boundary.
    """

    def __init__(self, action: str, *, limit: int, window_seconds: int) -> None:
        self._action = action
        self._limit = limit
        self._window_seconds = window_seconds

    async def __call__(self, request: Request, redis_client: redis.Redis = Depends(get_redis)) -> None:
        client_host = request.client.host if request.client else "unknown"
        key = f"rate_limit:{self._action}:{client_host}"
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, self._window_seconds)
        except RedisError:
            logger.warning("Rate limit check failed for key %s; allowing the request.", key, exc_info=True)
            return

        if count > self._limit:
            raise TooManyRequestsError(
                "Too many attempts. Please wait before trying again.",
                details={"retry_after_seconds": self._window_seconds},
            )
