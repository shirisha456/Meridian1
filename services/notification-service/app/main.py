import asyncio
import logging

import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from meridian_events import Topics

from app.config import get_settings
from app.consumer import process_message
from app.health import start_health_server
from app.logging_config import configure_logging
from app.metrics import errors_total
from app.tracing import continue_trace, setup_tracing

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)
    start_health_server(settings.health_check_port)
    setup_tracing(settings)

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
                with continue_trace("notification-service.process", message.headers):
                    await process_message(message.topic, message.value, redis_client)
            except Exception:
                # No dead-letter topic yet — same documented tradeoff as
                # enrichment-service and anomaly-service.
                errors_total.inc()
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
