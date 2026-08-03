import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

# Same minimal-column-subset, shared-database pattern as
# enrichment-service — see ADR-0007. The `alerts` table's declaration
# here (including its UniqueConstraint) must match apps/core-api's
# Alembic-managed schema exactly, since that constraint is what this
# service's idempotency guarantee actually rests on.
metadata = MetaData()

transactions_table = Table(
    "transactions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("account_id", Uuid),
    Column("category_id", Uuid, nullable=True),
    Column("merchant_name", String),
    Column("amount_minor", BigInteger),
    Column("txn_date", Date),
)

accounts_table = Table(
    "accounts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid),
)

alerts_table = Table(
    "alerts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid),
    Column("alert_type", Enum("duplicate_charge", "spend_spike", "subscription_price_increase", name="alert_type")),
    Column("severity", Enum("info", "warning", "critical", name="alert_severity")),
    Column("title", String),
    Column("detail", Text),
    Column("related_transaction_id", Uuid, nullable=True),
    Column("source_event_id", Uuid),
    Column("read_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("source_event_id", "alert_type", name="uq_alerts_source_event_id_alert_type"),
)


async def alert_exists(session: AsyncSession, source_event_id: UUID, alert_type: str) -> bool:
    existing = await session.scalar(
        select(alerts_table.c.id).where(
            alerts_table.c.source_event_id == source_event_id,
            alerts_table.c.alert_type == alert_type,
        )
    )
    return existing is not None


async def insert_alert(
    session: AsyncSession,
    *,
    user_id: UUID,
    alert_type: str,
    severity: str,
    title: str,
    detail: str,
    related_transaction_id: UUID | None,
    source_event_id: UUID,
) -> None:
    await session.execute(
        alerts_table.insert().values(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            detail=detail,
            related_transaction_id=related_transaction_id,
            source_event_id=source_event_id,
        )
    )
    await session.commit()


async def find_duplicate_charge(
    session: AsyncSession, account_id: UUID, merchant_name: str, amount_minor: int, txn_date: date, exclude_transaction_id: UUID
) -> UUID | None:
    """A same-account, same-merchant, same-amount transaction dated
    within a day of this one — the classic "swiped twice" pattern."""
    return await session.scalar(
        select(transactions_table.c.id)
        .where(
            transactions_table.c.account_id == account_id,
            transactions_table.c.merchant_name == merchant_name,
            transactions_table.c.amount_minor == amount_minor,
            transactions_table.c.id != exclude_transaction_id,
            transactions_table.c.txn_date >= txn_date - timedelta(days=1),
            transactions_table.c.txn_date <= txn_date + timedelta(days=1),
        )
        .limit(1)
    )


@dataclass
class CategorySpendStats:
    average_abs_amount_minor: float
    prior_count: int


async def get_category_spend_stats(
    session: AsyncSession, user_id: UUID, category_id: UUID, before: date, lookback_days: int = 90
) -> CategorySpendStats:
    cutoff = before - timedelta(days=lookback_days)
    row = (
        await session.execute(
            select(
                func.avg(func.abs(transactions_table.c.amount_minor)),
                func.count(),
            )
            .select_from(transactions_table)
            .join(accounts_table, accounts_table.c.id == transactions_table.c.account_id)
            .where(
                accounts_table.c.user_id == user_id,
                transactions_table.c.category_id == category_id,
                transactions_table.c.amount_minor < 0,
                transactions_table.c.txn_date >= cutoff,
                transactions_table.c.txn_date < before,
            )
        )
    ).one()
    average, count = row
    return CategorySpendStats(average_abs_amount_minor=float(average or 0), prior_count=count or 0)


async def get_previous_amount_for_merchant(
    session: AsyncSession, account_id: UUID, merchant_name: str, before: date, exclude_transaction_id: UUID
) -> int | None:
    return await session.scalar(
        select(transactions_table.c.amount_minor)
        .where(
            transactions_table.c.account_id == account_id,
            transactions_table.c.merchant_name == merchant_name,
            transactions_table.c.id != exclude_transaction_id,
            transactions_table.c.txn_date < before,
        )
        .order_by(transactions_table.c.txn_date.desc())
        .limit(1)
    )
