import logging
from typing import Protocol

import redis.asyncio as redis
from meridian_events import Topics, TransactionEnriched, TransactionIngested, to_json_bytes
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.categorizer import categorize_by_rules, categorize_with_ai_fallback
from app.config import Settings
from app.db import (
    count_prior_occurrences,
    fetch_transaction_context,
    get_category_id_by_name,
    set_transaction_category,
)

logger = logging.getLogger(__name__)

# A transaction is considered recurring once it's at least the 3rd time
# this exact merchant name has appeared on this account — a simple,
# explicitly heuristic (not ML) signal. Phase 9's anomaly-service is the
# actual consumer of this flag (subscription-price-increase detection).
RECURRING_THRESHOLD = 2


class KafkaProducer(Protocol):
    async def send_and_wait(self, topic: str, value: bytes, key: bytes | None = None) -> None: ...


async def process_message(
    payload: bytes,
    session_factory: async_sessionmaker[AsyncSession],
    producer: KafkaProducer,
    redis_client: redis.Redis,
    settings: Settings,
) -> None:
    event = TransactionIngested.model_validate_json(payload)

    async with session_factory() as session:
        context = await fetch_transaction_context(session, event.transaction_id)
        if context is None:
            # The transaction was deleted between being ingested and being
            # processed — nothing to enrich, not an error.
            logger.info("Transaction %s no longer exists; skipping.", event.transaction_id)
            return

        category_name = categorize_by_rules(context.merchant_name)
        if category_name is None:
            category_name = await categorize_with_ai_fallback(context.merchant_name, redis_client, settings)

        category_id = None
        if category_name is not None:
            category_id = await get_category_id_by_name(session, category_name)
            if category_id is None:
                logger.warning(
                    "Category %r not found in the categories table; leaving uncategorized.",
                    category_name,
                )

        prior_count = await count_prior_occurrences(
            session, context.account_id, context.merchant_name, context.txn_date
        )
        is_recurring = prior_count >= RECURRING_THRESHOLD

        if category_id is not None:
            await set_transaction_category(session, event.transaction_id, category_id)

    enriched = TransactionEnriched(
        transaction_id=event.transaction_id,
        account_id=event.account_id,
        user_id=event.user_id,
        merchant_name=event.merchant_name,
        amount_minor=event.amount_minor,
        currency=event.currency,
        txn_date=event.txn_date,
        category_id=category_id,
        category_name=category_name if category_id is not None else None,
        is_recurring=is_recurring,
    )
    await producer.send_and_wait(
        Topics.TRANSACTIONS_ENRICHED, value=to_json_bytes(enriched), key=str(event.user_id).encode()
    )
