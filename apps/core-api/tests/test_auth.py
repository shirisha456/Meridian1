REFRESH_COOKIE = "meridian_refresh_token"


async def _register(client, email="user@example.com", password="correct horse battery"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def test_register_creates_user_and_returns_tokens(authed_client):
    response = await _register(authed_client)
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "user@example.com"
    assert response.cookies.get(REFRESH_COOKIE) is not None


async def test_user_response_never_includes_password_hash(authed_client):
    response = await _register(authed_client)
    user = response.json()["user"]
    assert "password_hash" not in user
    assert "password" not in user


async def test_register_rejects_short_password(authed_client):
    response = await authed_client.post(
        "/api/v1/auth/register", json={"email": "short@example.com", "password": "abc"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"


async def test_register_duplicate_email_returns_409(authed_client):
    await _register(authed_client, email="dup@example.com")
    second = await _register(authed_client, email="dup@example.com")
    assert second.status_code == 409
    assert second.json()["error"]["type"] == "conflict"


async def test_login_success(authed_client):
    await _register(authed_client, email="login@example.com", password="correct horse battery")
    response = await authed_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_wrong_password_returns_401(authed_client):
    await _register(authed_client, email="wrongpw@example.com", password="correct horse battery")
    response = await authed_client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "definitely wrong"}
    )
    assert response.status_code == 401


async def test_login_unknown_email_gives_same_error_as_wrong_password(authed_client):
    # Same message for "no such account" and "wrong password" so a client
    # can't use the error to enumerate which emails have accounts.
    response = await authed_client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "whatever12345"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Incorrect email or password."


async def test_me_requires_auth(authed_client):
    response = await authed_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(authed_client):
    register_response = await _register(authed_client, email="me@example.com")
    access_token = register_response.json()["access_token"]

    response = await authed_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_refresh_cookie_is_httponly_samesite_scoped_to_auth_path(authed_client):
    response = await _register(authed_client, email="cookie@example.com")
    set_cookie = response.headers.get("set-cookie")
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "Path=/api/v1/auth" in set_cookie


async def test_refresh_rotates_token_and_rejects_reuse(authed_client):
    register_response = await _register(authed_client, email="reuse@example.com")
    old_refresh = register_response.cookies.get(REFRESH_COOKIE)
    assert old_refresh is not None

    refresh_response = await authed_client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    new_refresh = refresh_response.cookies.get(REFRESH_COOKIE)
    assert new_refresh is not None
    assert new_refresh != old_refresh

    # Legitimate rotation again, to prove rotation itself doesn't break
    # the session — and to have a "currently valid" token to check below.
    second_refresh_response = await authed_client.post("/api/v1/auth/refresh")
    assert second_refresh_response.status_code == 200
    latest_refresh = second_refresh_response.cookies.get(REFRESH_COOKIE)

    # Replay the *original* token — already rotated away once. This is
    # what a stolen-and-replayed refresh token looks like.
    authed_client.cookies.set(REFRESH_COOKIE, old_refresh)
    replay_response = await authed_client.post("/api/v1/auth/refresh")
    assert replay_response.status_code == 401
    assert "reuse" in replay_response.json()["error"]["message"].lower()

    # Reuse detection must kill the *entire* family, not just the replayed
    # token — so the legitimately-issued "latest_refresh" is dead too.
    authed_client.cookies.set(REFRESH_COOKIE, latest_refresh)
    killed_family_response = await authed_client.post("/api/v1/auth/refresh")
    assert killed_family_response.status_code == 401


async def test_refresh_without_cookie_returns_401(authed_client):
    response = await authed_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_revokes_refresh_token_server_side(authed_client):
    register_response = await _register(authed_client, email="logout@example.com")
    refresh_token = register_response.cookies.get(REFRESH_COOKIE)

    logout_response = await authed_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    # Present the token from before logout explicitly — proves it was
    # revoked server-side, not just that the client's cookie got cleared.
    authed_client.cookies.set(REFRESH_COOKIE, refresh_token)
    replay_response = await authed_client.post("/api/v1/auth/refresh")
    assert replay_response.status_code == 401
