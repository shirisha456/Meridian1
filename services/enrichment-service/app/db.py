from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import Column, Date, MetaData, String, Table, Uuid, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# This service does not own this schema and never runs migrations
# against it — apps/core-api's Alembic migrations are the single source
# of truth for these tables. Only the columns this service actually
# reads or writes are declared, deliberately, as a minimal-surface
# contract against a schema owned elsewhere. See ADR-0007.
metadata = MetaData()

transactions_table = Table(
    "transactions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("account_id", Uuid),
    Column("category_id", Uuid, nullable=True),
    Column("merchant_name", String),
    Column("txn_date", Date),
)

accounts_table = Table(
    "accounts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid),
)

categories_table = Table(
    "categories",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String),
)


@dataclass
class TransactionContext:
    account_id: UUID
    user_id: UUID
    merchant_name: str
    txn_date: date


async def fetch_transaction_context(
    session: AsyncSession, transaction_id: UUID
) -> TransactionContext | None:
    row = (
        await session.execute(
            select(
                transactions_table.c.account_id,
                accounts_table.c.user_id,
                transactions_table.c.merchant_name,
                transactions_table.c.txn_date,
            )
            .join(accounts_table, accounts_table.c.id == transactions_table.c.account_id)
            .where(transactions_table.c.id == transaction_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return TransactionContext(
        account_id=row.account_id,
        user_id=row.user_id,
        merchant_name=row.merchant_name,
        txn_date=row.txn_date,
    )


async def get_category_id_by_name(session: AsyncSession, name: str) -> UUID | None:
    return await session.scalar(select(categories_table.c.id).where(categories_table.c.name == name))


async def set_transaction_category(
    session: AsyncSession, transaction_id: UUID, category_id: UUID
) -> None:
    """A plain UPDATE-by-id — naturally idempotent. Reprocessing the same
    message (a real possibility under at-least-once delivery) just sets
    the same value again; no dedup table needed for this write."""
    await session.execute(
        update(transactions_table)
        .where(transactions_table.c.id == transaction_id)
        .values(category_id=category_id)
    )
    await session.commit()


async def count_prior_occurrences(
    session: AsyncSession, account_id: UUID, merchant_name: str, before: date
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(transactions_table)
        .where(
            transactions_table.c.account_id == account_id,
            transactions_table.c.merchant_name == merchant_name,
            transactions_table.c.txn_date < before,
        )
    )
    return count or 0
