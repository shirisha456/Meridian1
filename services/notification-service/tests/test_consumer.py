import json
from uuid import uuid4

import fakeredis.aioredis

from app.consumer import build_notification, process_message


def _alert_payload(user_id):
    return json.dumps(
        {
            "event_id": str(uuid4()),
            "version": 1,
            "user_id": str(user_id),
            "alert_type": "duplicate_charge",
            "severity": "warning",
            "title": "Possible duplicate charge",
            "detail": "Two charges within a day.",
        }
    ).encode()


def _insight_payload(user_id):
    return json.dumps(
        {
            "event_id": str(uuid4()),
            "version": 1,
            "user_id": str(user_id),
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "summary": "You spent $1,200 this month.",
        }
    ).encode()


def test_build_notification_maps_alerts_raised_to_alert_type():
    user_id = uuid4()
    result = build_notification("alerts.raised", _alert_payload(user_id))
    assert result is not None
    returned_user_id, notification = result
    assert returned_user_id == str(user_id)
    assert notification["type"] == "alert"
    assert notification["data"]["alert_type"] == "duplicate_charge"


def test_build_notification_maps_insights_generated_to_insight_type():
    user_id = uuid4()
    result = build_notification("insights.generated", _insight_payload(user_id))
    assert result is not None
    _, notification = result
    assert notification["type"] == "insight"


def test_build_notification_returns_none_for_unrecognized_topic():
    result = build_notification("some.other.topic", _alert_payload(uuid4()))
    assert result is None


async def test_process_message_publishes_to_the_users_channel():
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user_id = uuid4()

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"notifications:{user_id}")
    await pubsub.get_message(timeout=1)  # discard the subscribe confirmation

    published = await process_message("alerts.raised", _alert_payload(user_id), redis_client)
    assert published is True

    message = await pubsub.get_message(timeout=1)
    assert message is not None
    body = json.loads(message["data"])
    assert body["type"] == "alert"

    await pubsub.aclose()
    await redis_client.aclose()


async def test_process_message_on_unrecognized_topic_does_not_publish_or_raise():
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    published = await process_message("some.other.topic", _alert_payload(uuid4()), redis_client)
    assert published is False
    await redis_client.aclose()
