async def test_list_categories_requires_auth(authed_client):
    response = await authed_client.get("/api/v1/categories")
    assert response.status_code == 401


async def test_list_categories_returns_seeded_taxonomy_sorted_by_name(authed_client, auth_headers):
    response = await authed_client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == sorted(names)
    assert "Income" in names
    assert "Other" in names
    assert len(names) == 11


async def test_categories_are_shared_across_users_not_owned(authed_client, auth_headers):
    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    mine = await authed_client.get("/api/v1/categories", headers=auth_headers)
    theirs = await authed_client.get("/api/v1/categories", headers=other_headers)
    assert mine.json() == theirs.json()
