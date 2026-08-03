import json
from datetime import date
from uuid import uuid4

from meridian_events import (
    AlertRaised,
    InsightGenerated,
    Topics,
    TransactionEnriched,
    TransactionIngested,
    to_json_bytes,
)


def test_every_event_defaults_to_version_1():
    event = TransactionIngested(
        transaction_id=uuid4(),
        account_id=uuid4(),
        user_id=uuid4(),
        merchant_name="Coffee Shop",
        amount_minor=-450,
        currency="USD",
        txn_date=date(2026, 1, 15),
    )
    assert event.version == 1


def test_each_instance_gets_a_unique_event_id():
    kwargs = {
        "transaction_id": uuid4(),
        "account_id": uuid4(),
        "user_id": uuid4(),
        "merchant_name": "Coffee Shop",
        "amount_minor": -450,
        "currency": "USD",
        "txn_date": date(2026, 1, 15),
    }
    first = TransactionIngested(**kwargs)
    second = TransactionIngested(**kwargs)
    assert first.event_id != second.event_id


def test_to_json_bytes_round_trips_through_json():
    event = AlertRaised(
        user_id=uuid4(),
        alert_type="duplicate_charge",
        severity="warning",
        title="Possible duplicate charge",
        detail="Two $12.00 charges at Coffee Shop within a minute.",
    )
    payload = json.loads(to_json_bytes(event))
    assert payload["alert_type"] == "duplicate_charge"
    assert payload["event_id"] == str(event.event_id)


def test_transaction_enriched_allows_null_category_for_unmatched_merchants():
    event = TransactionEnriched(
        transaction_id=uuid4(),
        account_id=uuid4(),
        user_id=uuid4(),
        merchant_name="Some Obscure Merchant",
        amount_minor=-1200,
        currency="USD",
        txn_date=date(2026, 1, 15),
        category_id=None,
        category_name=None,
    )
    assert event.category_id is None
    assert event.is_recurring is False


def test_insight_generated_requires_a_period_and_summary():
    event = InsightGenerated(
        user_id=uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        summary="You spent $1,200 this month, mostly on dining out.",
    )
    assert event.period_start < event.period_end


def test_topics_all_lists_every_defined_topic():
    assert Topics.all() == [
        "transactions.ingested",
        "transactions.enriched",
        "alerts.raised",
        "insights.generated",
    ]
