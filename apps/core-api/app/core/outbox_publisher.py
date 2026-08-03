import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.kafka import KafkaProducer, get_kafka_producer
from app.core.outbox import OutboxEvent

logger = logging.getLogger(__name__)

PUBLISH_INTERVAL_SECONDS = 3
DEFAULT_BATCH_SIZE = 100


async def publish_pending_outbox_events(
    db: AsyncSession, producer: KafkaProducer, batch_size: int = DEFAULT_BATCH_SIZE
) -> int:
    """Publishes up to `batch_size` unpublished rows, oldest first.

    A row is only marked `published` in memory after `send_and_wait`
    actually confirms delivery — a producer failure on one row leaves it
    `published=False` (retried next cycle) without affecting any other
    row in the batch. The whole batch commits together at the end: a
    crash between a confirmed send and this commit causes that row to be
    republished (and its consumer to see a duplicate) on the next cycle
    — genuine at-least-once, never silent loss. See ADR-0005/0006.
    """
    result = await db.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.published.is_(False))
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
    )
    rows = list(result)

    published_count = 0
    for row in rows:
        try:
            await producer.send_and_wait(
                row.topic,
                value=json.dumps(row.payload).encode(),
                key=row.key.encode() if row.key else None,
            )
        except Exception:
            logger.exception(
                "Failed to publish outbox event %s to topic %s; will retry next cycle.",
                row.id,
                row.topic,
            )
            continue
        row.published = True
        published_count += 1

    if published_count:
        await db.commit()
    return published_count


async def run_outbox_publisher_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Runs until cancelled. Connection or publish failures are logged
    and retried next interval — never crash the app over a Kafka outage."""
    while True:
        try:
            producer = await get_kafka_producer()
            async with session_factory() as db:
                count = await publish_pending_outbox_events(db, producer)
                if count:
                    logger.info("Published %d outbox event(s).", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Outbox publisher iteration failed; will retry next interval.")
        await asyncio.sleep(PUBLISH_INTERVAL_SECONDS)
