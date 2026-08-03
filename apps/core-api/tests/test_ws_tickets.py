from uuid import uuid4

import fakeredis.aioredis

from app.core.ws_tickets import issue_ticket, redeem_ticket


async def test_ticket_redeems_to_the_issuing_user():
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user_id = uuid4()

    ticket = await issue_ticket(redis_client, user_id)
    redeemed = await redeem_ticket(redis_client, ticket)

    assert redeemed == user_id
    await redis_client.aclose()


async def test_ticket_is_single_use():
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user_id = uuid4()

    ticket = await issue_ticket(redis_client, user_id)
    await redeem_ticket(redis_client, ticket)
    second_attempt = await redeem_ticket(redis_client, ticket)

    assert second_attempt is None
    await redis_client.aclose()


async def test_unknown_ticket_returns_none():
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    result = await redeem_ticket(redis_client, "not-a-real-ticket")

    assert result is None
    await redis_client.aclose()


async def test_ws_ticket_endpoint_requires_auth(authed_client):
    response = await authed_client.post("/api/v1/auth/ws-ticket")
    assert response.status_code == 401


async def test_ws_ticket_endpoint_issues_a_ticket(authed_client, auth_headers):
    response = await authed_client.post("/api/v1/auth/ws-ticket", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ticket"]
    assert body["expires_in_seconds"] == 30
