from datetime import date
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.budgets.models import Budget
from app.budgets.schemas import BudgetActualItem
from app.categories.models import Category
from app.transactions.models import Transaction


def month_range(month: date) -> tuple[date, date]:
    """Returns (inclusive start, exclusive end) for the calendar month
    `month` falls in. `month` is expected already normalized to day=1."""
    if month.month == 12:
        next_month_start = date(month.year + 1, 1, 1)
    else:
        next_month_start = date(month.year, month.month + 1, 1)
    return month, next_month_start


async def compute_budget_actual(
    db: AsyncSession, user_id: UUID, month: date
) -> list[BudgetActualItem]:
    month_start, month_end = month_range(month)

    # Net spend per category: -(sum of transaction amounts), so a refund
    # (a positive amount) correctly offsets its original expense instead
    # of being counted as separate "income" against the budget.
    actual_subquery = (
        select(
            Transaction.category_id.label("category_id"),
            (-func.sum(Transaction.amount_minor)).label("actual_minor"),
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.txn_date >= month_start,
            Transaction.txn_date < month_end,
        )
        .group_by(Transaction.category_id)
        .subquery()
    )

    query = (
        select(
            Budget.category_id,
            Category.name,
            Budget.amount_minor,
            func.coalesce(actual_subquery.c.actual_minor, 0),
        )
        .join(Category, Category.id == Budget.category_id)
        .outerjoin(actual_subquery, actual_subquery.c.category_id == Budget.category_id)
        .where(Budget.user_id == user_id, Budget.month == month)
        .order_by(Category.name)
    )

    result = await db.execute(query)
    return [
        BudgetActualItem(
            category_id=category_id,
            category_name=category_name,
            budgeted_minor=budgeted_minor,
            actual_minor=actual_minor,
            remaining_minor=budgeted_minor - actual_minor,
        )
        for category_id, category_name, budgeted_minor, actual_minor in result
    ]


async def upsert_budget(
    db: AsyncSession, user_id: UUID, category_id: UUID, month: date, amount_minor: int
) -> Budget:
    existing = await db.scalar(
        select(Budget).where(
            and_(
                Budget.user_id == user_id,
                Budget.category_id == category_id,
                Budget.month == month,
            )
        )
    )
    if existing is not None:
        existing.amount_minor = amount_minor
        await db.commit()
        await db.refresh(existing)
        return existing

    budget = Budget(user_id=user_id, category_id=category_id, month=month, amount_minor=amount_minor)
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget
