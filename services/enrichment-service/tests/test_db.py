from datetime import date
from uuid import uuid4

from app.db import (
    accounts_table,
    categories_table,
    count_prior_occurrences,
    fetch_transaction_context,
    get_category_id_by_name,
    set_transaction_category,
    transactions_table,
)


async def _insert_account(session, account_id, user_id):
    await session.execute(accounts_table.insert().values(id=account_id, user_id=user_id))
    await session.commit()


async def _insert_transaction(session, txn_id, account_id, merchant_name, txn_date, category_id=None):
    await session.execute(
        transactions_table.insert().values(
            id=txn_id,
            account_id=account_id,
            category_id=category_id,
            merchant_name=merchant_name,
            txn_date=txn_date,
        )
    )
    await session.commit()


async def test_fetch_transaction_context_joins_account_for_user_id(session_factory):
    account_id, user_id, txn_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        await _insert_transaction(session, txn_id, account_id, "Coffee Shop", date(2026, 1, 15))

        context = await fetch_transaction_context(session, txn_id)

    assert context.account_id == account_id
    assert context.user_id == user_id
    assert context.merchant_name == "Coffee Shop"
    assert context.txn_date == date(2026, 1, 15)


async def test_fetch_transaction_context_returns_none_for_unknown_id(session_factory):
    async with session_factory() as session:
        context = await fetch_transaction_context(session, uuid4())
    assert context is None


async def test_get_category_id_by_name(session_factory):
    category_id = uuid4()
    async with session_factory() as session:
        await session.execute(categories_table.insert().values(id=category_id, name="Food & Dining"))
        await session.commit()

        found = await get_category_id_by_name(session, "Food & Dining")
        missing = await get_category_id_by_name(session, "Not A Category")

    assert found == category_id
    assert missing is None


async def test_set_transaction_category_updates_in_place(session_factory):
    account_id, user_id, txn_id, category_id = uuid4(), uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        await _insert_transaction(session, txn_id, account_id, "Coffee Shop", date(2026, 1, 15))

        await set_transaction_category(session, txn_id, category_id)
        # Idempotency check: setting the same category twice must not error.
        await set_transaction_category(session, txn_id, category_id)

        context_row = (
            await session.execute(transactions_table.select().where(transactions_table.c.id == txn_id))
        ).one()

    assert context_row.category_id == category_id


async def test_count_prior_occurrences_only_counts_earlier_same_account_same_merchant(session_factory):
    account_id, other_account_id, user_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_account(session, account_id, user_id)
        await _insert_account(session, other_account_id, user_id)

        await _insert_transaction(session, uuid4(), account_id, "Netflix", date(2026, 1, 1))
        await _insert_transaction(session, uuid4(), account_id, "Netflix", date(2026, 2, 1))
        # Different merchant — must not count.
        await _insert_transaction(session, uuid4(), account_id, "Spotify", date(2026, 1, 15))
        # Same merchant, different account — must not count.
        await _insert_transaction(session, uuid4(), other_account_id, "Netflix", date(2026, 1, 15))
        # On/after the reference date — must not count.
        await _insert_transaction(session, uuid4(), account_id, "Netflix", date(2026, 3, 1))

        count = await count_prior_occurrences(session, account_id, "Netflix", before=date(2026, 3, 1))

    assert count == 2
