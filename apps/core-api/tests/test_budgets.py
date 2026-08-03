async def _get_category_id(client, headers, name="Food & Dining"):
    response = await client.get("/api/v1/categories", headers=headers)
    return next(c["id"] for c in response.json() if c["name"] == name)


async def _create_account(client, headers):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "type": "checking", "currency": "USD", "current_balance_minor": 0},
        headers=headers,
    )
    return response.json()["id"]


async def _create_transaction(client, headers, account_id, category_id, amount_minor, txn_date):
    return await client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "merchant_name": "Test Merchant",
            "amount_minor": amount_minor,
            "currency": "USD",
            "txn_date": txn_date,
        },
        headers=headers,
    )


async def test_upsert_budget_creates_then_updates(authed_client, auth_headers):
    category_id = await _get_category_id(authed_client, auth_headers)

    first = await authed_client.put(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2026-01-15", "amount_minor": 50000},
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["amount_minor"] == 50000
    # month is normalized to the first of the month regardless of the day supplied
    assert first.json()["month"] == "2026-01-01"

    second = await authed_client.put(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2026-01-01", "amount_minor": 60000},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert second.json()["amount_minor"] == 60000
    assert second.json()["id"] == first.json()["id"]  # same row, updated not duplicated


async def test_list_budgets_for_month(authed_client, auth_headers):
    category_id = await _get_category_id(authed_client, auth_headers)
    await authed_client.put(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2026-01-01", "amount_minor": 50000},
        headers=auth_headers,
    )

    response = await authed_client.get("/api/v1/budgets?month=2026-01-01", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    empty = await authed_client.get("/api/v1/budgets?month=2026-02-01", headers=auth_headers)
    assert empty.json() == []


async def test_budget_actual_computes_net_spend_against_budget(authed_client, auth_headers):
    category_id = await _get_category_id(authed_client, auth_headers)
    account_id = await _create_account(authed_client, auth_headers)

    await authed_client.put(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2026-01-01", "amount_minor": 50000},
        headers=auth_headers,
    )
    await _create_transaction(authed_client, auth_headers, account_id, category_id, -12000, "2026-01-05")
    await _create_transaction(authed_client, auth_headers, account_id, category_id, -8000, "2026-01-20")
    # A refund (positive amount) should offset spend, not count as extra budget usage.
    await _create_transaction(authed_client, auth_headers, account_id, category_id, 3000, "2026-01-22")
    # Outside the month — must not be counted.
    await _create_transaction(authed_client, auth_headers, account_id, category_id, -99999, "2026-02-01")

    response = await authed_client.get("/api/v1/budgets/actual?month=2026-01-15", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert item["budgeted_minor"] == 50000
    assert item["actual_minor"] == 17000  # 12000 + 8000 - 3000
    assert item["remaining_minor"] == 33000


async def test_budget_actual_is_cached_until_a_transaction_invalidates_it(authed_client, auth_headers):
    category_id = await _get_category_id(authed_client, auth_headers)
    account_id = await _create_account(authed_client, auth_headers)
    await authed_client.put(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2026-01-01", "amount_minor": 50000},
        headers=auth_headers,
    )

    first = await authed_client.get("/api/v1/budgets/actual?month=2026-01-01", headers=auth_headers)
    assert first.json()[0]["actual_minor"] == 0

    await _create_transaction(authed_client, auth_headers, account_id, category_id, -5000, "2026-01-10")

    second = await authed_client.get("/api/v1/budgets/actual?month=2026-01-01", headers=auth_headers)
    assert second.json()[0]["actual_minor"] == 5000
