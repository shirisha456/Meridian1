async def _create_account(client, headers, name="Checking", type_="checking", balance=10000):
    return await client.post(
        "/api/v1/accounts",
        json={"name": name, "type": type_, "currency": "USD", "current_balance_minor": balance},
        headers=headers,
    )


async def test_create_account(authed_client, auth_headers):
    response = await _create_account(authed_client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Checking"
    assert body["type"] == "checking"
    assert body["current_balance_minor"] == 10000


async def test_create_account_requires_auth(authed_client):
    response = await authed_client.post(
        "/api/v1/accounts", json={"name": "Checking", "type": "checking"}
    )
    assert response.status_code == 401


async def test_list_accounts_is_paginated(authed_client, auth_headers):
    for i in range(3):
        await _create_account(authed_client, auth_headers, name=f"Account {i}")

    response = await authed_client.get("/api/v1/accounts?limit=2&offset=0", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2

    second_page = await authed_client.get("/api/v1/accounts?limit=2&offset=2", headers=auth_headers)
    assert len(second_page.json()["items"]) == 1


async def test_get_update_delete_account(authed_client, auth_headers):
    create_response = await _create_account(authed_client, auth_headers)
    account_id = create_response.json()["id"]

    get_response = await authed_client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert get_response.status_code == 200

    patch_response = await authed_client.patch(
        f"/api/v1/accounts/{account_id}", json={"name": "Renamed"}, headers=auth_headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Renamed"

    delete_response = await authed_client.delete(
        f"/api/v1/accounts/{account_id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    after_delete = await authed_client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert after_delete.status_code == 404


async def test_cannot_access_another_users_account(authed_client, auth_headers):
    create_response = await _create_account(authed_client, auth_headers)
    account_id = create_response.json()["id"]

    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    # 404, not 403 — never confirm the resource exists for a non-owner.
    get_response = await authed_client.get(f"/api/v1/accounts/{account_id}", headers=other_headers)
    assert get_response.status_code == 404

    patch_response = await authed_client.patch(
        f"/api/v1/accounts/{account_id}", json={"name": "Hijacked"}, headers=other_headers
    )
    assert patch_response.status_code == 404

    delete_response = await authed_client.delete(
        f"/api/v1/accounts/{account_id}", headers=other_headers
    )
    assert delete_response.status_code == 404

    # And the account is genuinely untouched.
    still_there = await authed_client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "Checking"


async def test_accounts_list_only_shows_own_accounts(authed_client, auth_headers):
    await _create_account(authed_client, auth_headers, name="Mine")

    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}
    await _create_account(authed_client, other_headers, name="Theirs")

    response = await authed_client.get("/api/v1/accounts", headers=auth_headers)
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["Mine"]
