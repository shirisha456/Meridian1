import asyncio
import logging
import sys

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from meridian_events import Topics
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    consumer = AIOKafkaConsumer(
        Topics.TRANSACTIONS_ENRICHED,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)

    await consumer.start()
    await producer.start()
    logger.info("anomaly-service started, consuming %s", Topics.TRANSACTIONS_ENRICHED)

    try:
        async for message in consumer:
            try:
                raised = await process_message(message.value, session_factory, producer)
                if raised:
                    logger.info("Raised %d alert(s) from offset %d.", raised, message.offset)
            except Exception:
                # No dead-letter topic yet — same documented tradeoff as
                # enrichment-service (docs/phase8.md, docs/phase9.md).
                logger.exception(
                    "Failed to process message at offset %d; skipping.", message.offset
                )
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
