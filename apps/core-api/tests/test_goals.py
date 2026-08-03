async def _create_goal(client, headers, name="Emergency Fund", target=500000):
    return await client.post(
        "/api/v1/goals",
        json={"name": name, "target_amount_minor": target, "current_amount_minor": 0},
        headers=headers,
    )


async def test_create_and_list_goals(authed_client, auth_headers):
    response = await _create_goal(authed_client, auth_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Emergency Fund"

    listing = await authed_client.get("/api/v1/goals", headers=auth_headers)
    assert listing.json()["total"] == 1


async def test_update_goal_progress(authed_client, auth_headers):
    create_response = await _create_goal(authed_client, auth_headers)
    goal_id = create_response.json()["id"]

    patch_response = await authed_client.patch(
        f"/api/v1/goals/{goal_id}", json={"current_amount_minor": 25000}, headers=auth_headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["current_amount_minor"] == 25000


async def test_delete_goal(authed_client, auth_headers):
    create_response = await _create_goal(authed_client, auth_headers)
    goal_id = create_response.json()["id"]

    delete_response = await authed_client.delete(f"/api/v1/goals/{goal_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    listing = await authed_client.get("/api/v1/goals", headers=auth_headers)
    assert listing.json()["total"] == 0


async def test_cannot_modify_another_users_goal(authed_client, auth_headers):
    create_response = await _create_goal(authed_client, auth_headers)
    goal_id = create_response.json()["id"]

    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    patch_response = await authed_client.patch(
        f"/api/v1/goals/{goal_id}", json={"name": "Hijacked"}, headers=other_headers
    )
    assert patch_response.status_code == 404

    delete_response = await authed_client.delete(f"/api/v1/goals/{goal_id}", headers=other_headers)
    assert delete_response.status_code == 404
