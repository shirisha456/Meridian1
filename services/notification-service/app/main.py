import asyncio
import logging
import sys

import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from meridian_events import Topics

from app.config import get_settings
from app.consumer import process_message
from app.health import start_health_server

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    start_health_server(settings.health_check_port)

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    consumer = AIOKafkaConsumer(
        Topics.ALERTS_RAISED,
        Topics.INSIGHTS_GENERATED,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info(
        "notification-service started, consuming %s and %s",
        Topics.ALERTS_RAISED,
        Topics.INSIGHTS_GENERATED,
    )

    try:
        async for message in consumer:
            try:
                await process_message(message.topic, message.value, redis_client)
            except Exception:
                # No dead-letter topic yet — same documented tradeoff as
                # enrichment-service and anomaly-service.
                logger.exception(
                    "Failed to process message at offset %d on %s; skipping.",
                    message.offset,
                    message.topic,
                )
            await consumer.commit()
    finally:
        await consumer.stop()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
