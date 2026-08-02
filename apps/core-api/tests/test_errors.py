from app.errors.exceptions import NotFoundError
from app.errors.handlers import app_error_handler, unhandled_exception_handler


async def test_unknown_route_returns_error_envelope(client):
    response = await client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "not_found"
    assert "message" in body["error"]


async def test_app_error_handler_builds_documented_envelope():
    exc = NotFoundError("Account not found.", details={"account_id": "abc-123"})
    response = await app_error_handler(request=None, exc=exc)
    assert response.status_code == 404
    body = response.body.decode()
    assert '"type":"not_found"' in body.replace(" ", "")
    assert "Account not found." in body
    assert "abc-123" in body


async def test_unhandled_exception_never_leaks_details_to_client():
    secret_bearing_exc = RuntimeError("connection failed: password=hunter2")
    response = await unhandled_exception_handler(request=_FakeRequest(), exc=secret_bearing_exc)
    assert response.status_code == 500
    body = response.body.decode()
    assert "hunter2" not in body
    assert "An unexpected error occurred." in body


class _FakeRequest:
    method = "GET"

    class _URL:
        path = "/fake"

    url = _URL()
