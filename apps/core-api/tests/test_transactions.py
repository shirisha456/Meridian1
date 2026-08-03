async def _create_account(client, headers, name="Checking"):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "checking", "currency": "USD", "current_balance_minor": 0},
        headers=headers,
    )
    return response.json()["id"]


async def _create_transaction(client, headers, account_id, **overrides):
    payload = {
        "account_id": account_id,
        "merchant_name": "Coffee Shop",
        "amount_minor": -450,
        "currency": "USD",
        "txn_date": "2026-01-15",
    }
    payload.update(overrides)
    return await client.post("/api/v1/transactions", json=payload, headers=headers)


async def test_create_and_get_transaction(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    response = await _create_transaction(authed_client, auth_headers, account_id)
    assert response.status_code == 201
    body = response.json()
    assert body["merchant_name"] == "Coffee Shop"
    assert body["amount_minor"] == -450

    get_response = await authed_client.get(f"/api/v1/transactions/{body['id']}", headers=auth_headers)
    assert get_response.status_code == 200


async def test_cannot_create_transaction_on_another_users_account(authed_client, auth_headers):
    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}
    other_account_id = await _create_account(authed_client, other_headers, name="Victim's account")

    # auth_headers' user tries to post a transaction onto an account they
    # don't own, by guessing/reusing its id.
    response = await _create_transaction(authed_client, auth_headers, other_account_id)
    assert response.status_code == 404


async def test_cannot_access_another_users_transaction(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    create_response = await _create_transaction(authed_client, auth_headers, account_id)
    transaction_id = create_response.json()["id"]

    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    get_response = await authed_client.get(
        f"/api/v1/transactions/{transaction_id}", headers=other_headers
    )
    assert get_response.status_code == 404

    patch_response = await authed_client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"merchant_name": "Hijacked"}, headers=other_headers
    )
    assert patch_response.status_code == 404

    delete_response = await authed_client.delete(
        f"/api/v1/transactions/{transaction_id}", headers=other_headers
    )
    assert delete_response.status_code == 404


async def test_list_transactions_filters_by_merchant_search(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    await _create_transaction(authed_client, auth_headers, account_id, merchant_name="Blue Bottle Coffee")
    await _create_transaction(authed_client, auth_headers, account_id, merchant_name="Whole Foods")

    response = await authed_client.get("/api/v1/transactions?q=coffee", headers=auth_headers)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["merchant_name"] == "Blue Bottle Coffee"


async def test_list_transactions_filters_by_date_range(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    await _create_transaction(authed_client, auth_headers, account_id, txn_date="2026-01-01")
    await _create_transaction(authed_client, auth_headers, account_id, txn_date="2026-02-01")

    response = await authed_client.get(
        "/api/v1/transactions?date_from=2026-01-15&date_to=2026-02-15", headers=auth_headers
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["txn_date"] == "2026-02-01"


async def test_list_transactions_is_paginated_and_ordered_newest_first(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    await _create_transaction(authed_client, auth_headers, account_id, txn_date="2026-01-01")
    await _create_transaction(authed_client, auth_headers, account_id, txn_date="2026-03-01")
    await _create_transaction(authed_client, auth_headers, account_id, txn_date="2026-02-01")

    response = await authed_client.get("/api/v1/transactions?limit=2", headers=auth_headers)
    body = response.json()
    assert body["total"] == 3
    assert [item["txn_date"] for item in body["items"]] == ["2026-03-01", "2026-02-01"]


async def test_delete_transaction(authed_client, auth_headers):
    account_id = await _create_account(authed_client, auth_headers)
    create_response = await _create_transaction(authed_client, auth_headers, account_id)
    transaction_id = create_response.json()["id"]

    delete_response = await authed_client.delete(
        f"/api/v1/transactions/{transaction_id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    after_delete = await authed_client.get(
        f"/api/v1/transactions/{transaction_id}", headers=auth_headers
    )
    assert after_delete.status_code == 404
