import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.health import start_health_server
from app.logging_config import configure_logging
from app.poller import poll_once
from app.provider import get_provider
from app.tracing import poll_cycle_span, setup_tracing

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)
    start_health_server(settings.health_check_port)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    setup_tracing(settings, engine.sync_engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = get_provider(settings.market_data_api_key, settings.market_data_base_url)

    logger.info(
        "market-data-service started, polling every %ds (provider configured: %s)",
        settings.poll_interval_seconds,
        provider is not None,
    )

    try:
        while True:
            try:
                with poll_cycle_span("market-data-service.poll"):
                    async with session_factory() as session:
                        await poll_once(session, provider)
            except Exception:
                # Same "log and continue" shape as the three Kafka-consuming
                # services' message-processing loops — one failed cycle
                # (e.g. the provider is briefly down) shouldn't kill the
                # process; the next scheduled cycle just tries again.
                logger.exception("Poll cycle failed; will retry next cycle.")
            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
