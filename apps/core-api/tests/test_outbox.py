import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.outbox import OutboxEvent, write_outbox_event
from app.core.outbox_publisher import publish_pending_outbox_events


class FakeKafkaProducer:
    def __init__(self, fail_topics: set[str] | None = None):
        self.sent: list[tuple[str, bytes, bytes | None]] = []
        self.fail_topics = fail_topics or set()

    async def send_and_wait(self, topic, value, key=None):
        if topic in self.fail_topics:
            raise RuntimeError("simulated broker failure")
        self.sent.append((topic, value, key))


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_write_outbox_event_is_not_published_until_publisher_runs(db_session):
    write_outbox_event(db_session, topic="transactions.ingested", key="acct-1", payload={"a": 1})
    await db_session.commit()

    row = await db_session.scalar(select(OutboxEvent))
    assert row.published is False


async def test_publish_pending_outbox_events_marks_successful_sends_published(db_session):
    write_outbox_event(db_session, topic="transactions.ingested", key="acct-1", payload={"a": 1})
    await db_session.commit()

    fake_producer = FakeKafkaProducer()
    count = await publish_pending_outbox_events(db_session, fake_producer)

    assert count == 1
    assert len(fake_producer.sent) == 1
    assert fake_producer.sent[0][0] == "transactions.ingested"

    row = await db_session.scalar(select(OutboxEvent))
    assert row.published is True


async def test_publish_failure_leaves_that_row_unpublished_without_blocking_others(db_session):
    write_outbox_event(db_session, topic="topic.a", key="k1", payload={"x": 1})
    write_outbox_event(db_session, topic="topic.b", key="k2", payload={"x": 2})
    await db_session.commit()

    fake_producer = FakeKafkaProducer(fail_topics={"topic.a"})
    count = await publish_pending_outbox_events(db_session, fake_producer)

    assert count == 1  # only topic.b succeeded
    rows = {row.topic: row.published for row in (await db_session.scalars(select(OutboxEvent))).all()}
    assert rows["topic.a"] is False  # left for retry next cycle
    assert rows["topic.b"] is True


async def test_already_published_rows_are_not_republished(db_session):
    write_outbox_event(db_session, topic="topic.a", key="k1", payload={"x": 1})
    await db_session.commit()

    fake_producer = FakeKafkaProducer()
    await publish_pending_outbox_events(db_session, fake_producer)
    second_run_count = await publish_pending_outbox_events(db_session, fake_producer)

    assert second_run_count == 0
    assert len(fake_producer.sent) == 1


async def _create_account(client, headers):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "type": "checking", "currency": "USD", "current_balance_minor": 0},
        headers=headers,
    )
    return response.json()["id"]


async def test_creating_uncategorized_transaction_writes_a_transactions_ingested_event(
    authed_client, auth_headers, db_engine
):
    account_id = await _create_account(authed_client, auth_headers)

    await authed_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "merchant_name": "Coffee Shop",
            "amount_minor": -450,
            "currency": "USD",
            "txn_date": "2026-01-15",
        },
        headers=auth_headers,
    )

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        row = await session.scalar(select(OutboxEvent))

    assert row is not None
    assert row.topic == "transactions.ingested"
    assert row.published is False
    assert row.payload["merchant_name"] == "Coffee Shop"
    assert row.payload["amount_minor"] == -450
    assert row.payload["version"] == 1


async def test_creating_categorized_transaction_writes_no_event(
    authed_client, auth_headers, db_engine
):
    account_id = await _create_account(authed_client, auth_headers)
    categories = await authed_client.get("/api/v1/categories", headers=auth_headers)
    category_id = categories.json()[0]["id"]

    await authed_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "merchant_name": "Coffee Shop",
            "amount_minor": -450,
            "currency": "USD",
            "txn_date": "2026-01-15",
        },
        headers=auth_headers,
    )

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        row = await session.scalar(select(OutboxEvent))

    assert row is None  # already categorized — nothing for enrichment to do
