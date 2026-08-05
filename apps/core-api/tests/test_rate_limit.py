from app.core.redis import get_redis
from tests.conftest import broken_redis


async def _register(client, email="user@example.com", password="correct horse battery"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def test_register_allows_requests_under_the_limit(authed_client):
    for i in range(5):
        response = await _register(authed_client, email=f"under-limit-{i}@example.com")
        assert response.status_code == 201


async def test_register_blocks_the_request_that_exceeds_the_limit(authed_client):
    for i in range(5):
        await _register(authed_client, email=f"at-limit-{i}@example.com")

    sixth = await _register(authed_client, email="over-limit@example.com")

    assert sixth.status_code == 429
    body = sixth.json()
    assert body["error"]["type"] == "too_many_requests"
    assert "retry_after_seconds" in body["error"]["details"]


async def test_login_has_a_higher_ceiling_than_register(authed_client):
    await _register(authed_client, email="repeat-login@example.com", password="correct horse battery")

    # Fewer than the login limit (10) but more than register's (5) — proves
    # login and register are tracked independently, not sharing one counter.
    for _ in range(8):
        response = await authed_client.post(
            "/api/v1/auth/login",
            json={"email": "repeat-login@example.com", "password": "wrong on purpose"},
        )
        assert response.status_code == 401


async def test_rate_limit_is_scoped_per_action_not_shared(authed_client):
    """Exhausting the register limit must not also block login — they're
    different keys (rate_limit:register:* vs rate_limit:login:*)."""
    await _register(authed_client, email="scoped-user@example.com", password="correct horse battery")
    for i in range(5):
        await _register(authed_client, email=f"scoped-{i}@example.com")
    assert (await _register(authed_client, email="scoped-blocked@example.com")).status_code == 429

    login_response = await authed_client.post(
        "/api/v1/auth/login",
        json={"email": "scoped-user@example.com", "password": "correct horse battery"},
    )
    assert login_response.status_code == 200


async def test_rate_limit_fails_open_when_redis_is_unreachable(authed_client, app):
    """ADR-0002: a Redis outage degrades rate limiting, it does not make
    login/register unavailable — the single most critical path in the app
    must not depend on Redis's uptime."""
    app.dependency_overrides[get_redis] = broken_redis

    for i in range(20):
        response = await _register(authed_client, email=f"redis-down-{i}@example.com")
        assert response.status_code == 201
