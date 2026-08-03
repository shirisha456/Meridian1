from datetime import date
from uuid import uuid4

from app.db import (
    accounts_table,
    alert_exists,
    find_duplicate_charge,
    get_category_spend_stats,
    get_previous_amount_for_merchant,
    insert_alert,
    transactions_table,
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


async def test_alert_exists_and_insert_alert_idempotency_key(session_factory):
    user_id, event_id = uuid4(), uuid4()
    async with session_factory() as session:
        assert await alert_exists(session, event_id, "duplicate_charge") is False

        await insert_alert(
            session,
            user_id=user_id,
            alert_type="duplicate_charge",
            severity="warning",
            title="t",
            detail="d",
            related_transaction_id=None,
            source_event_id=event_id,
        )

        assert await alert_exists(session, event_id, "duplicate_charge") is True
        # A different alert_type for the SAME event is a distinct thing —
        # must not be considered "already exists".
        assert await alert_exists(session, event_id, "spend_spike") is False


async def test_find_duplicate_charge_matches_same_account_merchant_amount_within_a_day(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        first_id = uuid4()
        await _insert_txn(session, first_id, account_id, "Coffee Shop", -450, date(2026, 1, 15))

        second_id = uuid4()
        await _insert_txn(session, second_id, account_id, "Coffee Shop", -450, date(2026, 1, 15))

        found = await find_duplicate_charge(
            session, account_id, "Coffee Shop", -450, date(2026, 1, 15), exclude_transaction_id=second_id
        )
    assert found == first_id


async def test_find_duplicate_charge_ignores_different_amount(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        await _insert_txn(session, uuid4(), account_id, "Coffee Shop", -450, date(2026, 1, 15))

        found = await find_duplicate_charge(
            session, account_id, "Coffee Shop", -999, date(2026, 1, 15), exclude_transaction_id=uuid4()
        )
    assert found is None


async def test_category_spend_stats_only_counts_this_users_expenses_in_window(session_factory):
    user_id, other_user_id = uuid4(), uuid4()
    account_id, other_account_id = uuid4(), uuid4()
    category_id, other_category_id = uuid4(), uuid4()

    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        await _insert_account(session, other_account_id, other_user_id)

        for i in range(5):
            await _insert_txn(
                session, uuid4(), account_id, "Grocery", -2000, date(2026, 1, 1 + i), category_id=category_id
            )
        # Different category — excluded.
        await _insert_txn(session, uuid4(), account_id, "Movies", -1500, date(2026, 1, 10), category_id=other_category_id)
        # Different user — excluded.
        await _insert_txn(session, uuid4(), other_account_id, "Grocery", -5000, date(2026, 1, 10), category_id=category_id)
        # Income (positive) — excluded.
        await _insert_txn(session, uuid4(), account_id, "Refund", 2000, date(2026, 1, 10), category_id=category_id)
        # Outside the 90-day window — excluded.
        await _insert_txn(session, uuid4(), account_id, "Grocery", -2000, date(2025, 1, 1), category_id=category_id)

        stats = await get_category_spend_stats(session, user_id, category_id, before=date(2026, 2, 1))

    assert stats.prior_count == 5
    assert stats.average_abs_amount_minor == 2000.0


async def test_get_previous_amount_for_merchant_returns_most_recent_prior(session_factory):
    account_id = uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, uuid4())
        await _insert_txn(session, uuid4(), account_id, "Netflix", -1500, date(2026, 1, 1))
        await _insert_txn(session, uuid4(), account_id, "Netflix", -1600, date(2026, 2, 1))
        current_id = uuid4()
        await _insert_txn(session, current_id, account_id, "Netflix", -1700, date(2026, 3, 1))

        previous = await get_previous_amount_for_merchant(
            session, account_id, "Netflix", before=date(2026, 3, 1), exclude_transaction_id=current_id
        )
    assert previous == -1600  # the most recent one before March, not January
