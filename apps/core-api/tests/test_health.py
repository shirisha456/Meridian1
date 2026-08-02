from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from tests.conftest import broken_db_session, sqlite_session


async def test_live_always_ok(client):
    response = await client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_200_when_database_reachable(app):
    app.dependency_overrides[get_db] = sqlite_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] is True


async def test_ready_returns_503_when_database_unreachable(app):
    app.dependency_overrides[get_db] = broken_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] is False


async def test_health_reports_ok_when_database_reachable(app):
    app.dependency_overrides[get_db] = sqlite_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_reports_degraded_but_returns_200_when_database_unreachable(app):
    # /health is for dashboards/humans, not orchestrators — it stays 200
    # and reports state in the body so a monitoring tool can scrape it
    # even while the database is down, rather than treating the endpoint
    # itself as failed.
    app.dependency_overrides[get_db] = broken_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] is False
