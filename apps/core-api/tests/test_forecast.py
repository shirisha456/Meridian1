from datetime import UTC, datetime, timedelta


async def _create_account(client, headers, type_="checking", balance=0):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": type_, "type": type_, "currency": "USD", "current_balance_minor": balance},
        headers=headers,
    )
    return response.json()["id"]


async def _create_transaction(client, headers, account_id, amount_minor, txn_date, merchant):
    return await client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "merchant_name": merchant,
            "amount_minor": amount_minor,
            "currency": "USD",
            "txn_date": txn_date,
        },
        headers=headers,
    )


TODAY = datetime.now(UTC).date()


async def _seed_monthly_subscription(client, headers, account_id, merchant="Netflix", amount_minor=-1599):
    """Three occurrences ~30 days apart, most recent 10 days before TODAY —
    the minimum signal needed to be picked up as recurring."""
    for i in range(3):
        txn_date = TODAY - timedelta(days=10 + (2 - i) * 30)
        await _create_transaction(client, headers, account_id, amount_minor, txn_date.isoformat(), merchant)


async def test_forecast_requires_auth(authed_client):
    response = await authed_client.get("/api/v1/forecast")
    assert response.status_code == 401


async def test_forecast_starting_balance_sums_only_spendable_account_types(authed_client, auth_headers):
    await _create_account(authed_client, auth_headers, "checking", 100000)
    await _create_account(authed_client, auth_headers, "savings", 50000)
    await _create_account(authed_client, auth_headers, "investment", 999999)  # excluded: not liquid
    await _create_account(authed_client, auth_headers, "credit", 20000)  # excluded: a liability

    response = await authed_client.get("/api/v1/forecast", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["starting_balance_minor"] == 150000


async def test_forecast_with_no_transactions_projects_a_flat_line_at_starting_balance(
    authed_client, auth_headers
):
    await _create_account(authed_client, auth_headers, "checking", 100000)

    response = await authed_client.get("/api/v1/forecast?horizon_days=30", headers=auth_headers)
    body = response.json()
    assert body["recurring_items"] == []
    assert body["projected_ending_balance_minor"] == 100000
    assert len(body["daily_projection"]) == 31  # as_of plus 30 days, inclusive


async def test_two_occurrences_is_not_enough_to_be_recurring(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers, "checking", 100000)
    await _create_transaction(
        authed_client, auth_headers, account_id, -1599, (TODAY - timedelta(days=40)).isoformat(), "Netflix"
    )
    await _create_transaction(
        authed_client, auth_headers, account_id, -1599, (TODAY - timedelta(days=10)).isoformat(), "Netflix"
    )

    response = await authed_client.get("/api/v1/forecast", headers=auth_headers)
    assert response.json()["recurring_items"] == []


async def test_third_occurrence_is_detected_as_recurring_and_projected_forward(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers, "checking", 100000)
    await _seed_monthly_subscription(authed_client, auth_headers, account_id)

    response = await authed_client.get("/api/v1/forecast?horizon_days=60", headers=auth_headers)
    body = response.json()

    assert len(body["recurring_items"]) == 1
    item = body["recurring_items"][0]
    assert item["merchant_name"] == "Netflix"
    assert item["average_amount_minor"] == -1599
    assert item["occurrences"] == 3
    assert 25 <= item["average_interval_days"] <= 35

    # Balance should drop by the subscription amount at least once within
    # a 60-day horizon of a ~30-day-interval pattern.
    ending = body["projected_ending_balance_minor"]
    assert ending < body["starting_balance_minor"]


async def test_recurring_income_increases_the_projection(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers, "checking", 100000)
    for i in range(3):
        txn_date = TODAY - timedelta(days=10 + (2 - i) * 14)
        await _create_transaction(authed_client, auth_headers, account_id, 200000, txn_date.isoformat(), "Employer Payroll")

    response = await authed_client.get("/api/v1/forecast?horizon_days=30", headers=auth_headers)
    body = response.json()
    assert body["projected_ending_balance_minor"] > body["starting_balance_minor"]


async def test_horizon_days_is_bounded(authed_client, auth_headers):
    await _create_account(authed_client, auth_headers, "checking", 100000)

    too_long = await authed_client.get("/api/v1/forecast?horizon_days=181", headers=auth_headers)
    assert too_long.status_code == 422

    zero = await authed_client.get("/api/v1/forecast?horizon_days=0", headers=auth_headers)
    assert zero.status_code == 422
