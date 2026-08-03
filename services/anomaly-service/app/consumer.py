import logging
from typing import Protocol

from meridian_events import AlertRaised, Topics, TransactionEnriched, to_json_bytes
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import alert_exists, insert_alert
from app.rules import ALL_RULES

logger = logging.getLogger(__name__)


class KafkaProducer(Protocol):
    async def send_and_wait(self, topic: str, value: bytes, key: bytes | None = None) -> None: ...


async def process_message(
    payload: bytes,
    session_factory: async_sessionmaker[AsyncSession],
    producer: KafkaProducer,
) -> int:
    """Returns the number of new alerts raised (0 is a normal, common
    result — most transactions aren't anomalous)."""
    event = TransactionEnriched.model_validate_json(payload)

    raised = 0
    async with session_factory() as session:
        for rule in ALL_RULES:
            candidate = await rule(session, event)
            if candidate is None:
                continue

            # The idempotency fix: check-then-insert keyed on
            # (event.event_id, alert_type), backed by the real unique
            # constraint apps/core-api's migration creates on that same
            # pair. A redelivery of this exact message re-evaluates the
            # same rules and finds the alert already exists, rather than
            # creating a duplicate — the bug the reference
            # implementation's anomaly-service had despite its own ADR
            # claiming otherwise.
            if await alert_exists(session, event.event_id, candidate.alert_type):
                logger.info(
                    "Alert %s for event %s already exists; skipping (redelivery).",
                    candidate.alert_type,
                    event.event_id,
                )
                continue

            await insert_alert(
                session,
                user_id=event.user_id,
                alert_type=candidate.alert_type,
                severity=candidate.severity,
                title=candidate.title,
                detail=candidate.detail,
                related_transaction_id=candidate.related_transaction_id,
                source_event_id=event.event_id,
            )

            alert_event = AlertRaised(
                user_id=event.user_id,
                alert_type=candidate.alert_type,
                severity=candidate.severity,
                title=candidate.title,
                detail=candidate.detail,
                related_transaction_id=candidate.related_transaction_id,
            )
            await producer.send_and_wait(
                Topics.ALERTS_RAISED, value=to_json_bytes(alert_event), key=str(event.user_id).encode()
            )
            raised += 1

    return raised
