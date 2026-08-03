import secrets
from uuid import UUID

import redis.asyncio as redis

TICKET_TTL_SECONDS = 30


def _ticket_key(ticket: str) -> str:
    return f"ws_ticket:{ticket}"


async def issue_ticket(redis_client: redis.Redis, user_id: UUID) -> str:
    ticket = secrets.token_urlsafe(32)
    await redis_client.set(_ticket_key(ticket), str(user_id), ex=TICKET_TTL_SECONDS)
    return ticket


async def redeem_ticket(redis_client: redis.Redis, ticket: str) -> UUID | None:
    """Deliberately does NOT fail open on a Redis error, unlike
    app/core/cache.py (ADR-0002). ADR-0002 scopes itself to cache-shaped
    uses where a miss just means recomputing something; this is an auth
    check, where "Redis is down" must mean "reject the connection," not
    "let it through." A RedisError here propagates and the WebSocket
    handshake fails closed."""
    key = _ticket_key(ticket)
    user_id_str = await redis_client.get(key)
    if user_id_str is None:
        return None
    await redis_client.delete(key)  # single-use
    return UUID(user_id_str)
