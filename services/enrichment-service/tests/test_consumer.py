import json
from datetime import date
from uuid import uuid4

import fakeredis.aioredis
import pytest
from meridian_events import TransactionIngested, to_json_bytes

from app.config import Settings
from app.consumer import process_message
from app.db import accounts_table, categories_table, transactions_table


class FakeProducer:
    def __init__(self):
        self.sent: list[tuple[str, bytes, bytes | None]] = []

    async def send_and_wait(self, topic, value, key=None):
        self.sent.append((topic, value, key))


@pytest.fixture
def settings():
    return Settings(openai_api_key="")  # rules-only for these tests


async def _seed(session, account_id, user_id, txn_id, merchant_name, txn_date=date(2026, 1, 15)):
    await session.execute(accounts_table.insert().values(id=account_id, user_id=user_id))
    await session.execute(
        transactions_table.insert().values(
            id=txn_id, account_id=account_id, category_id=None, merchant_name=merchant_name, txn_date=txn_date
        )
    )
    await session.execute(categories_table.insert().values(id=uuid4(), name="Food & Dining"))
    await session.commit()


async def test_process_message_categorizes_and_publishes_enriched_event(session_factory, settings):
    account_id, user_id, txn_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _seed(session, account_id, user_id, txn_id, "Starbucks")

    event = TransactionIngested(
        transaction_id=txn_id,
        account_id=account_id,
        user_id=user_id,
        merchant_name="Starbucks",
        amount_minor=-450,
        currency="USD",
        txn_date=date(2026, 1, 15),
    )

    producer = FakeProducer()
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    await process_message(to_json_bytes(event), session_factory, producer, redis_client, settings)

    assert len(producer.sent) == 1
    topic, value, key = producer.sent[0]
    assert topic == "transactions.enriched"
    assert key == str(user_id).encode()
    enriched = json.loads(value)
    assert enriched["category_name"] == "Food & Dining"
    assert enriched["category_id"] is not None
    assert enriched["is_recurring"] is False

    async with session_factory() as session:
        row = (
            await session.execute(transactions_table.select().where(transactions_table.c.id == txn_id))
        ).one()
    assert row.category_id is not None

    await redis_client.aclose()


async def test_process_message_leaves_transaction_uncategorized_when_no_rule_matches(
    session_factory, settings
):
    account_id, user_id, txn_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _seed(session, account_id, user_id, txn_id, "Some Obscure Merchant XYZ")

    event = TransactionIngested(
        transaction_id=txn_id,
        account_id=account_id,
        user_id=user_id,
        merchant_name="Some Obscure Merchant XYZ",
        amount_minor=-1200,
        currency="USD",
        txn_date=date(2026, 1, 15),
    )

    producer = FakeProducer()
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    await process_message(to_json_bytes(event), session_factory, producer, redis_client, settings)

    enriched = json.loads(producer.sent[0][1])
    assert enriched["category_id"] is None
    assert enriched["category_name"] is None

    async with session_factory() as session:
        row = (
            await session.execute(transactions_table.select().where(transactions_table.c.id == txn_id))
        ).one()
    assert row.category_id is None

    await redis_client.aclose()


async def test_process_message_flags_recurring_after_threshold(session_factory, settings):
    account_id, user_id = uuid4(), uuid4()
    async with session_factory() as session:
        await session.execute(accounts_table.insert().values(id=account_id, user_id=user_id))
        await session.execute(categories_table.insert().values(id=uuid4(), name="Food & Dining"))
        # Two PRIOR occurrences of the same merchant on the same account.
        await session.execute(
            transactions_table.insert().values(
                id=uuid4(), account_id=account_id, category_id=None,
                merchant_name="Starbucks", txn_date=date(2026, 1, 1),
            )
        )
        await session.execute(
            transactions_table.insert().values(
                id=uuid4(), account_id=account_id, category_id=None,
                merchant_name="Starbucks", txn_date=date(2026, 1, 8),
            )
        )
        third_txn_id = uuid4()
        await session.execute(
            transactions_table.insert().values(
                id=third_txn_id, account_id=account_id, category_id=None,
                merchant_name="Starbucks", txn_date=date(2026, 1, 15),
            )
        )
        await session.commit()

    event = TransactionIngested(
        transaction_id=third_txn_id,
        account_id=account_id,
        user_id=user_id,
        merchant_name="Starbucks",
        amount_minor=-450,
        currency="USD",
        txn_date=date(2026, 1, 15),
    )

    producer = FakeProducer()
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    await process_message(to_json_bytes(event), session_factory, producer, redis_client, settings)

    enriched = json.loads(producer.sent[0][1])
    assert enriched["is_recurring"] is True

    await redis_client.aclose()


async def test_process_message_is_idempotent_on_redelivery(session_factory, settings):
    """The real idempotency guarantee: reprocessing the same message
    (a genuine possibility under at-least-once delivery) must not error
    and must leave the transaction in the same correct state — a second
    UPDATE-by-id, not a duplicate insert anywhere."""
    account_id, user_id, txn_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _seed(session, account_id, user_id, txn_id, "Starbucks")

    event = TransactionIngested(
        transaction_id=txn_id,
        account_id=account_id,
        user_id=user_id,
        merchant_name="Starbucks",
        amount_minor=-450,
        currency="USD",
        txn_date=date(2026, 1, 15),
    )
    payload = to_json_bytes(event)
    producer = FakeProducer()
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    await process_message(payload, session_factory, producer, redis_client, settings)
    await process_message(payload, session_factory, producer, redis_client, settings)

    assert len(producer.sent) == 2  # both publishes happen — at-least-once is expected
    first = json.loads(producer.sent[0][1])
    second = json.loads(producer.sent[1][1])
    assert first["category_id"] == second["category_id"]  # same resulting state, not divergent

    await redis_client.aclose()


async def test_process_message_skips_gracefully_when_transaction_no_longer_exists(
    session_factory, settings
):
    event = TransactionIngested(
        transaction_id=uuid4(),
        account_id=uuid4(),
        user_id=uuid4(),
        merchant_name="Ghost Merchant",
        amount_minor=-100,
        currency="USD",
        txn_date=date(2026, 1, 15),
    )
    producer = FakeProducer()
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    await process_message(to_json_bytes(event), session_factory, producer, redis_client, settings)

    assert producer.sent == []  # nothing published; nothing crashed

    await redis_client.aclose()
