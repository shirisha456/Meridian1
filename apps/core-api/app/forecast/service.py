from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account, AccountType
from app.categories.models import Category
from app.forecast.schemas import ForecastPoint, ForecastResponse, RecurringItem
from app.transactions.models import Transaction

# Same signal enrichment-service uses for the is_recurring flag on
# TransactionEnriched (RECURRING_THRESHOLD there is "count >= 2 prior
# occurrences", i.e. the 3rd+ time a merchant appears) — kept as a
# forecast-local constant rather than importing across the service
# boundary (ADR-0007: core-api doesn't depend on a consumer service's
# internals, and that flag isn't persisted back to this DB anyway).
MIN_OCCURRENCES_TO_BE_RECURRING = 3

# How far back to look for a recurring pattern. Long enough to catch a
# monthly (~30-day) subscription needing 3 occurrences (~60-90 days of
# history), short enough that a merchant the user stopped using 6 months
# ago doesn't still show up as "recurring."
LOOKBACK_DAYS = 120

# The account types a cash-flow forecast should draw from: money that's
# actually spendable near-term. Investment balances are excluded (not
# liquid on a day-to-day basis) and credit/loan balances are excluded
# (they're liabilities, not spendable funds — a recurring transaction
# paying down a card already shows up as its own expense line if one
# exists, so including the balance itself would double count it).
SPENDABLE_ACCOUNT_TYPES = (AccountType.checking, AccountType.savings, AccountType.cash)


@dataclass
class _RecurringPattern:
    merchant_name: str
    category_name: str | None
    average_amount_minor: int
    occurrences: int
    average_interval_days: float
    last_seen: date


async def _starting_balance(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(Account.current_balance_minor), 0)).where(
            Account.user_id == user_id, Account.type.in_(SPENDABLE_ACCOUNT_TYPES)
        )
    )
    return int(result.scalar_one())


async def _detect_recurring_patterns(db: AsyncSession, user_id: UUID, as_of: date) -> list[_RecurringPattern]:
    """Grounded in real transaction history, not guessed — the same
    "compute it for real, don't hallucinate a number" philosophy Phase 10's
    insights feature follows (ADR-0008), applied to pattern detection
    instead of an LLM summary.

    A merchant is a candidate once it has at least
    MIN_OCCURRENCES_TO_BE_RECURRING transactions within LOOKBACK_DAYS;
    its average interval is the span between its first and last
    occurrence divided by (count - 1), which is what determines how far
    apart its projected future occurrences are placed.
    """
    lookback_start = as_of - timedelta(days=LOOKBACK_DAYS)

    rows = await db.execute(
        select(
            Transaction.merchant_name,
            Category.name.label("category_name"),
            func.count().label("occurrences"),
            func.avg(Transaction.amount_minor).label("average_amount"),
            func.min(Transaction.txn_date).label("first_date"),
            func.max(Transaction.txn_date).label("last_date"),
        )
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Account.user_id == user_id,
            Transaction.txn_date >= lookback_start,
            Transaction.txn_date <= as_of,
        )
        .group_by(Transaction.merchant_name, Category.name)
        .having(func.count() >= MIN_OCCURRENCES_TO_BE_RECURRING)
    )

    patterns: list[_RecurringPattern] = []
    for row in rows:
        span_days = (row.last_date - row.first_date).days
        if span_days <= 0:
            # Every occurrence landed on the same date — not enough
            # signal to infer a recurrence interval from.
            continue
        average_interval_days = span_days / (row.occurrences - 1)
        if average_interval_days < 1:
            continue
        patterns.append(
            _RecurringPattern(
                merchant_name=row.merchant_name,
                category_name=row.category_name,
                average_amount_minor=round(row.average_amount),
                occurrences=row.occurrences,
                average_interval_days=average_interval_days,
                last_seen=row.last_date,
            )
        )
    return patterns


def _project_occurrence_dates(pattern: _RecurringPattern, as_of: date, horizon_end: date) -> list[date]:
    """Walks forward from the pattern's last real occurrence in steps of
    its average interval, collecting every projected date that falls
    inside the forecast window. round(), not int(), on the interval so a
    ~29.5-day pattern doesn't systematically drift early by rounding
    down every single step."""
    dates: list[date] = []
    step_days = max(1, round(pattern.average_interval_days))
    next_date = pattern.last_seen + timedelta(days=step_days)
    while next_date <= horizon_end:
        if next_date > as_of:
            dates.append(next_date)
        next_date += timedelta(days=step_days)
    return dates


async def build_forecast(db: AsyncSession, user_id: UUID, *, as_of: date, horizon_days: int) -> ForecastResponse:
    starting_balance_minor = await _starting_balance(db, user_id)
    horizon_end = as_of + timedelta(days=horizon_days)
    patterns = await _detect_recurring_patterns(db, user_id, as_of)

    # date -> total signed amount_minor landing on that date, across every
    # recurring pattern — a merchant with two independent recurring
    # patterns (rare, but not impossible) both correctly contribute.
    amounts_by_date: dict[date, int] = {}
    recurring_items: list[RecurringItem] = []
    for pattern in patterns:
        occurrence_dates = _project_occurrence_dates(pattern, as_of, horizon_end)
        for occurrence_date in occurrence_dates:
            amounts_by_date[occurrence_date] = amounts_by_date.get(occurrence_date, 0) + pattern.average_amount_minor

        recurring_items.append(
            RecurringItem(
                merchant_name=pattern.merchant_name,
                category_name=pattern.category_name,
                average_amount_minor=pattern.average_amount_minor,
                occurrences=pattern.occurrences,
                average_interval_days=round(pattern.average_interval_days, 1),
                last_seen=pattern.last_seen,
                next_expected_date=occurrence_dates[0] if occurrence_dates else pattern.last_seen,
            )
        )

    daily_projection: list[ForecastPoint] = []
    running_balance = starting_balance_minor
    current_date = as_of
    while current_date <= horizon_end:
        running_balance += amounts_by_date.get(current_date, 0)
        daily_projection.append(ForecastPoint(date=current_date, projected_balance_minor=running_balance))
        current_date += timedelta(days=1)

    return ForecastResponse(
        as_of=as_of,
        horizon_days=horizon_days,
        starting_balance_minor=starting_balance_minor,
        projected_ending_balance_minor=daily_projection[-1].projected_balance_minor
        if daily_projection
        else starting_balance_minor,
        recurring_items=sorted(recurring_items, key=lambda item: item.next_expected_date),
        daily_projection=daily_projection,
    )
