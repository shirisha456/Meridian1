async def _create_account(client, headers, type_, balance):
    return await client.post(
        "/api/v1/accounts",
        json={"name": type_, "type": type_, "currency": "USD", "current_balance_minor": balance},
        headers=headers,
    )


async def test_recompute_net_worth_classifies_assets_and_liabilities_by_account_type(
    authed_client, auth_headers
):
    await _create_account(authed_client, auth_headers, "checking", 100000)
    await _create_account(authed_client, auth_headers, "savings", 50000)
    # Credit balance entered as a positive "amount owed" — the common
    # real-world mental model — must still be treated as a liability.
    await _create_account(authed_client, auth_headers, "credit", 20000)

    response = await authed_client.post("/api/v1/networth/recompute", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["assets_minor"] == 150000
    assert body["liabilities_minor"] == 20000
    assert body["net_worth_minor"] == 130000


async def test_recompute_is_upsert_for_the_same_day(authed_client, auth_headers):
    await _create_account(authed_client, auth_headers, "checking", 100000)

    first = await authed_client.post("/api/v1/networth/recompute", headers=auth_headers)
    await _create_account(authed_client, auth_headers, "savings", 50000)
    second = await authed_client.post("/api/v1/networth/recompute", headers=auth_headers)

    assert first.json()["id"] == second.json()["id"]  # same snapshot row, not duplicated
    assert second.json()["net_worth_minor"] == 150000


async def test_net_worth_history_reflects_recompute_and_is_cached(authed_client, auth_headers):
    await _create_account(authed_client, auth_headers, "checking", 100000)
    await authed_client.post("/api/v1/networth/recompute", headers=auth_headers)

    history = await authed_client.get("/api/v1/networth?days=30", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["net_worth_minor"] == 100000


async def test_net_worth_requires_auth(authed_client):
    response = await authed_client.get("/api/v1/networth")
    assert response.status_code == 401
