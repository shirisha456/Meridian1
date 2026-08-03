import logging
from typing import Protocol

from aiokafka import AIOKafkaProducer

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class KafkaProducer(Protocol):
    async def send_and_wait(self, topic: str, value: bytes, key: bytes | None = None) -> None: ...


_producer: AIOKafkaProducer | None = None


async def get_kafka_producer() -> AIOKafkaProducer:
    """Lazily starts a single shared producer on first use rather than
    at app startup — so the API still boots and serves every non-Kafka
    request normally even if Redpanda isn't running (the same
    degrade-gracefully posture as every other optional dependency in
    this app). The outbox publisher loop is the only caller; a failed
    connection attempt here just means that loop's next iteration logs
    a warning and retries, not that the app fails to start.
    """
    global _producer
    if _producer is None:
        producer = AIOKafkaProducer(bootstrap_servers=get_settings().kafka_bootstrap_servers)
        await producer.start()
        _producer = producer
    return _producer


async def stop_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
