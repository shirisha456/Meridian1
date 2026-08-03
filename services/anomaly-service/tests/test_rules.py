from datetime import date
from uuid import uuid4

from meridian_events import TransactionEnriched

from app.db import accounts_table, transactions_table
from app.rules import (
    detect_duplicate_charge,
    detect_spend_spike,
    detect_subscription_price_increase,
)


async def _insert_account(session, account_id, user_id):
    await session.execute(accounts_table.insert().values(id=account_id, user_id=user_id))
    await session.commit()


async def _insert_txn(session, txn_id, account_id, merchant_name, amount_minor, txn_date, category_id=None):
    await session.execute(
        transactions_table.insert().values(
            id=txn_id,
            account_id=account_id,
            category_id=category_id,
            merchant_name=merchant_name,
            amount_minor=amount_minor,
            txn_date=txn_date,
        )
    )
    await session.commit()


def _enriched(**overrides):
    defaults = {
        "transaction_id": uuid4(),
        "account_id": uuid4(),
        "user_id": uuid4(),
        "merchant_name": "Merchant",
        "amount_minor": -1000,
        "currency": "USD",
        "txn_date": date(2026, 1, 15),
        "category_id": None,
        "category_name": None,
        "is_recurring": False,
    }
    defaults.update(overrides)
    return TransactionEnriched(**defaults)


async def test_detect_duplicate_charge_fires_on_a_real_duplicate(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        await _insert_txn(session, uuid4(), account_id, "Coffee Shop", -450, date(2026, 1, 15))

        event = _enriched(account_id=account_id, merchant_name="Coffee Shop", amount_minor=-450)
        alert = await detect_duplicate_charge(session, event)

    assert alert is not None
    assert alert.alert_type == "duplicate_charge"


async def test_detect_duplicate_charge_does_not_fire_without_a_match(session_factory):
    async with session_factory() as session:
        event = _enriched()
        alert = await detect_duplicate_charge(session, event)
    assert alert is None


async def test_detect_spend_spike_fires_when_amount_exceeds_3x_average(session_factory):
    account_id, user_id, category_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        for i in range(5):
            await _insert_txn(
                session, uuid4(), account_id, "Grocery", -2000, date(2026, 1, 1 + i), category_id=category_id
            )

        event = _enriched(
            account_id=account_id,
            user_id=user_id,
            category_id=category_id,
            amount_minor=-10000,  # 5x the 2000 average
            txn_date=date(2026, 2, 1),
        )
        alert = await detect_spend_spike(session, event)

    assert alert is not None
    assert alert.alert_type == "spend_spike"


async def test_detect_spend_spike_does_not_fire_below_threshold_multiplier(session_factory):
    account_id, user_id, category_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        for i in range(5):
            await _insert_txn(
                session, uuid4(), account_id, "Grocery", -2000, date(2026, 1, 1 + i), category_id=category_id
            )

        event = _enriched(
            account_id=account_id,
            user_id=user_id,
            category_id=category_id,
            amount_minor=-3000,  # only 1.5x — below the 3x threshold
            txn_date=date(2026, 2, 1),
        )
        alert = await detect_spend_spike(session, event)

    assert alert is None


async def test_detect_spend_spike_does_not_fire_below_minimum_history(session_factory):
    account_id, user_id, category_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        # Only 2 prior transactions — below SPEND_SPIKE_MIN_PRIOR_TRANSACTIONS (5).
        for i in range(2):
            await _insert_txn(
                session, uuid4(), account_id, "Grocery", -2000, date(2026, 1, 1 + i), category_id=category_id
            )

        event = _enriched(
            account_id=account_id, user_id=user_id, category_id=category_id,
            amount_minor=-50000, txn_date=date(2026, 2, 1),
        )
        alert = await detect_spend_spike(session, event)

    assert alert is None


async def test_detect_subscription_price_increase_fires_above_5_percent(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        await _insert_txn(session, uuid4(), account_id, "Netflix", -1500, date(2026, 1, 1))

        event = _enriched(
            account_id=account_id, merchant_name="Netflix", amount_minor=-1800,  # 20% higher
            is_recurring=True, txn_date=date(2026, 2, 1),
        )
        alert = await detect_subscription_price_increase(session, event)

    assert alert is not None
    assert alert.alert_type == "subscription_price_increase"


async def test_detect_subscription_price_increase_requires_is_recurring(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        await _insert_txn(session, uuid4(), account_id, "Netflix", -1500, date(2026, 1, 1))

        event = _enriched(
            account_id=account_id, merchant_name="Netflix", amount_minor=-1800,
            is_recurring=False,  # not flagged as recurring by enrichment-service
            txn_date=date(2026, 2, 1),
        )
        alert = await detect_subscription_price_increase(session, event)

    assert alert is None


async def test_detect_subscription_price_increase_does_not_fire_for_small_bump(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        await _insert_txn(session, uuid4(), account_id, "Netflix", -1500, date(2026, 1, 1))

        event = _enriched(
            account_id=account_id, merchant_name="Netflix", amount_minor=-1520,  # ~1.3% higher
            is_recurring=True, txn_date=date(2026, 2, 1),
        )
        alert = await detect_subscription_price_increase(session, event)

    assert alert is None
