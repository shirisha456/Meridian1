from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.outbox import OutboxEvent


async def _create_account(client, headers):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "type": "checking", "currency": "USD", "current_balance_minor": 0},
        headers=headers,
    )
    return response.json()["id"]


async def _get_category_id(client, headers, name="Food & Dining"):
    response = await client.get("/api/v1/categories", headers=headers)
    return next(c["id"] for c in response.json() if c["name"] == name)


async def _create_categorized_transaction(client, headers, account_id, category_id, amount_minor, txn_date, merchant="Coffee Shop"):
    return await client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "merchant_name": merchant,
            "amount_minor": amount_minor,
            "currency": "USD",
            "txn_date": txn_date,
        },
        headers=headers,
    )


async def test_latest_insight_returns_404_when_none_generated_yet(authed_client, auth_headers):
    response = await authed_client.get("/api/v1/insights/latest", headers=auth_headers)
    assert response.status_code == 404


async def test_generate_returns_422_with_no_categorized_spending(authed_client, auth_headers):
    response = await authed_client.post(
        "/api/v1/insights/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-02-01"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "unprocessable"


async def test_generate_uses_template_fallback_when_openai_not_configured(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    category_id = await _get_category_id(authed_client, auth_headers)
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -1200, "2026-01-10"
    )
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -3400, "2026-01-15", merchant="Grocery Store"
    )

    response = await authed_client.post(
        "/api/v1/insights/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-02-01"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert "January 2026" in body["summary"]
    assert "$46.00" in body["summary"]  # (12.00 + 34.00) total spend
    assert "Food & Dining" in body["summary"]


async def test_generate_defaults_to_current_month_when_period_omitted(authed_client, auth_headers, app):
    account_id = await _create_account(authed_client, auth_headers)
    category_id = await _get_category_id(authed_client, auth_headers)
    today = datetime.now(UTC).date()
    this_month_first = today.replace(day=1)
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -500, this_month_first.isoformat()
    )

    response = await authed_client.post("/api/v1/insights/generate", json={}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["period_start"] == this_month_first.isoformat()


async def test_generate_excludes_uncategorized_and_out_of_period_transactions(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    category_id = await _get_category_id(authed_client, auth_headers)

    # In period, categorized — counts.
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -1000, "2026-01-10"
    )
    # Uncategorized — must not count.
    await authed_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id, "merchant_name": "Mystery", "amount_minor": -99999,
            "currency": "USD", "txn_date": "2026-01-12",
        },
        headers=auth_headers,
    )
    # Outside the period — must not count.
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -50000, "2026-02-05"
    )

    response = await authed_client.post(
        "/api/v1/insights/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-02-01"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert "$10.00" in response.json()["summary"]


async def test_get_latest_returns_the_most_recently_generated_insight(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    category_id = await _get_category_id(authed_client, auth_headers)
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -1000, "2026-01-10"
    )
    await authed_client.post(
        "/api/v1/insights/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-02-01"},
        headers=auth_headers,
    )
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -2000, "2026-02-10"
    )
    second = await authed_client.post(
        "/api/v1/insights/generate",
        json={"period_start": "2026-02-01", "period_end": "2026-03-01"},
        headers=auth_headers,
    )

    latest = await authed_client.get("/api/v1/insights/latest", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["id"]


async def test_generate_writes_an_outbox_event(authed_client, auth_headers, db_engine):
    account_id = await _create_account(authed_client, auth_headers)
    category_id = await _get_category_id(authed_client, auth_headers)
    await _create_categorized_transaction(
        authed_client, auth_headers, account_id, category_id, -1000, "2026-01-10"
    )

    await authed_client.post(
        "/api/v1/insights/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-02-01"},
        headers=auth_headers,
    )

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        row = await session.scalar(select(OutboxEvent).where(OutboxEvent.topic == "insights.generated"))
    assert row is not None
    assert row.payload["period_start"] == "2026-01-01"


async def test_insights_endpoints_require_auth(authed_client):
    response = await authed_client.get("/api/v1/insights/latest")
    assert response.status_code == 401
