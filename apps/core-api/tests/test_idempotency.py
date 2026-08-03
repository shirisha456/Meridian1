from app.core.redis import get_redis
from tests.conftest import broken_redis


async def _create_account(client, headers):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "type": "checking", "currency": "USD", "current_balance_minor": 0},
        headers=headers,
    )
    return response.json()["id"]


async def test_same_idempotency_key_returns_the_same_transaction_not_a_duplicate(
    authed_client, auth_headers
):
    account_id = await _create_account(authed_client, auth_headers)
    payload = {
        "account_id": account_id,
        "merchant_name": "Coffee Shop",
        "amount_minor": -450,
        "currency": "USD",
        "txn_date": "2026-01-15",
    }
    headers = {**auth_headers, "Idempotency-Key": "client-retry-abc123"}

    first = await authed_client.post("/api/v1/transactions", json=payload, headers=headers)
    second = await authed_client.post("/api/v1/transactions", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    listing = await authed_client.get(
        f"/api/v1/transactions?account_id={account_id}", headers=auth_headers
    )
    assert listing.json()["total"] == 1


async def test_different_idempotency_keys_create_separate_transactions(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    payload = {
        "account_id": account_id,
        "merchant_name": "Coffee Shop",
        "amount_minor": -450,
        "currency": "USD",
        "txn_date": "2026-01-15",
    }

    first = await authed_client.post(
        "/api/v1/transactions", json=payload, headers={**auth_headers, "Idempotency-Key": "key-1"}
    )
    second = await authed_client.post(
        "/api/v1/transactions", json=payload, headers={**auth_headers, "Idempotency-Key": "key-2"}
    )

    assert first.json()["id"] != second.json()["id"]


async def test_no_idempotency_key_creates_separate_transactions_each_time(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    payload = {
        "account_id": account_id,
        "merchant_name": "Coffee Shop",
        "amount_minor": -450,
        "currency": "USD",
        "txn_date": "2026-01-15",
    }

    first = await authed_client.post("/api/v1/transactions", json=payload, headers=auth_headers)
    second = await authed_client.post("/api/v1/transactions", json=payload, headers=auth_headers)

    assert first.json()["id"] != second.json()["id"]


async def test_idempotency_fails_open_when_redis_is_unreachable(authed_client, auth_headers, app):
    """ADR-0002: a Redis outage degrades idempotency protection, it does
    not turn transaction creation into a 500/503."""
    app.dependency_overrides[get_redis] = broken_redis

    account_id = await _create_account(authed_client, auth_headers)
    response = await authed_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "merchant_name": "Coffee Shop",
            "amount_minor": -450,
            "currency": "USD",
            "txn_date": "2026-01-15",
        },
        headers={**auth_headers, "Idempotency-Key": "irrelevant-because-redis-is-down"},
    )
    assert response.status_code == 201
