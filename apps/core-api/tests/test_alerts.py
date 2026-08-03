from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.alerts.models import Alert, AlertSeverity, AlertType


async def _seed_alert(db_engine, user_id, alert_type=AlertType.duplicate_charge, read_at=None):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        alert = Alert(
            user_id=user_id,
            alert_type=alert_type,
            severity=AlertSeverity.warning,
            title="Possible duplicate charge",
            detail="Two $12.00 charges at Coffee Shop within a day.",
            source_event_id=uuid4(),
            read_at=read_at,
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return alert.id


async def _get_user_id(client, headers) -> UUID:
    response = await client.get("/api/v1/auth/me", headers=headers)
    return UUID(response.json()["id"])


async def test_list_alerts_requires_auth(authed_client):
    response = await authed_client.get("/api/v1/alerts")
    assert response.status_code == 401


async def test_list_alerts_returns_own_alerts_only(authed_client, auth_headers, db_engine):
    user_id = await _get_user_id(authed_client, auth_headers)
    await _seed_alert(db_engine, user_id)

    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}
    other_user_id = await _get_user_id(authed_client, other_headers)
    await _seed_alert(db_engine, other_user_id)

    response = await authed_client.get("/api/v1/alerts", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_unread_only_filter(authed_client, auth_headers, db_engine):
    user_id = await _get_user_id(authed_client, auth_headers)
    await _seed_alert(db_engine, user_id, alert_type=AlertType.spend_spike, read_at=datetime.now(UTC))
    unread_id = await _seed_alert(db_engine, user_id, alert_type=AlertType.duplicate_charge)

    response = await authed_client.get("/api/v1/alerts?unread_only=true", headers=auth_headers)
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(unread_id)


async def test_mark_alert_read(authed_client, auth_headers, db_engine):
    user_id = await _get_user_id(authed_client, auth_headers)
    alert_id = await _seed_alert(db_engine, user_id)

    response = await authed_client.patch(f"/api/v1/alerts/{alert_id}/read", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    listing = await authed_client.get("/api/v1/alerts?unread_only=true", headers=auth_headers)
    assert listing.json() == []


async def test_cannot_mark_another_users_alert_read(authed_client, auth_headers, db_engine):
    user_id = await _get_user_id(authed_client, auth_headers)
    alert_id = await _seed_alert(db_engine, user_id)

    other_register = await authed_client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@example.com", "password": "correct horse battery"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    response = await authed_client.patch(f"/api/v1/alerts/{alert_id}/read", headers=other_headers)
    assert response.status_code == 404
