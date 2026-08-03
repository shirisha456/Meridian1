import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from meridian_events import InsightGenerated, Topics
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.categories.models import Category
from app.core.config import Settings
from app.core.outbox import write_outbox_event
from app.errors import UnprocessableError
from app.insights.models import Insight
from app.transactions.models import Transaction

logger = logging.getLogger(__name__)


@dataclass
class CategoryTotal:
    category_name: str
    total_minor: int


@dataclass
class MerchantTotal:
    merchant_name: str
    total_minor: int


@dataclass
class PeriodAggregates:
    total_spend_minor: int
    category_totals: list[CategoryTotal]
    top_merchants: list[MerchantTotal]


def resolve_period(period_start: date | None, period_end: date | None) -> tuple[date, date]:
    """Defaults to the current calendar month when either bound is
    omitted. period_end is exclusive, matching app/budgets/service.py's
    month_range convention."""
    if period_start is None:
        today = datetime.now(UTC).date()
        period_start = today.replace(day=1)
    if period_end is None:
        period_end = (
            date(period_start.year + 1, 1, 1)
            if period_start.month == 12
            else date(period_start.year, period_start.month + 1, 1)
        )
    return period_start, period_end


async def compute_period_aggregates(
    db: AsyncSession, user_id: UUID, period_start: date, period_end: date
) -> PeriodAggregates:
    """Only categorized expenses count — both for the numbers shown and
    for whether there's anything to summarize at all. Uncategorized
    spending has no category to attribute it to, so including it would
    make "top category" numbers misleadingly incomplete."""
    spend_total = -Transaction.amount_minor  # positive magnitude of an expense

    category_rows = (
        await db.execute(
            select(Category.name, func.sum(spend_total))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.user_id == user_id,
                Transaction.txn_date >= period_start,
                Transaction.txn_date < period_end,
                Transaction.amount_minor < 0,
                Transaction.category_id.is_not(None),
            )
            .group_by(Category.name)
            .order_by(func.sum(spend_total).desc())
        )
    ).all()

    merchant_rows = (
        await db.execute(
            select(Transaction.merchant_name, func.sum(spend_total))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.user_id == user_id,
                Transaction.txn_date >= period_start,
                Transaction.txn_date < period_end,
                Transaction.amount_minor < 0,
                Transaction.category_id.is_not(None),
            )
            .group_by(Transaction.merchant_name)
            .order_by(func.sum(spend_total).desc())
            .limit(5)
        )
    ).all()

    category_totals = [CategoryTotal(name, int(total)) for name, total in category_rows]
    top_merchants = [MerchantTotal(name, int(total)) for name, total in merchant_rows]
    total_spend = sum(c.total_minor for c in category_totals)

    return PeriodAggregates(
        total_spend_minor=total_spend, category_totals=category_totals, top_merchants=top_merchants
    )


def template_summary(period_start: date, aggregates: PeriodAggregates) -> str:
    """A pure, deterministic fallback — no external call, no chance of
    inventing a number. Used whenever OpenAI isn't configured or fails,
    so the insights feature is never fully dead."""
    month_label = period_start.strftime("%B %Y")
    total = aggregates.total_spend_minor / 100
    sentences = [
        (
            f"In {month_label}, you spent ${total:,.2f} across "
            f"{len(aggregates.category_totals)} categor{'y' if len(aggregates.category_totals) == 1 else 'ies'}."
        )
    ]
    if aggregates.category_totals:
        top = aggregates.category_totals[0]
        sentences.append(f"Your top category was {top.category_name} at ${top.total_minor / 100:,.2f}.")
    if aggregates.top_merchants:
        top = aggregates.top_merchants[0]
        sentences.append(f"Your top merchant was {top.merchant_name} at ${top.total_minor / 100:,.2f}.")
    return " ".join(sentences)


async def ai_summary(
    period_start: date, aggregates: PeriodAggregates, settings: Settings
) -> str | None:
    """Sends only pre-computed aggregates, never raw transaction rows —
    grounded generation, not free-form. Returns None (never raises) on
    any failure so the caller always has the template fallback."""
    if not settings.openai_api_key:
        return None

    category_lines = "\n".join(
        f"- {c.category_name}: ${c.total_minor / 100:,.2f}" for c in aggregates.category_totals
    )
    merchant_lines = "\n".join(
        f"- {m.merchant_name}: ${m.total_minor / 100:,.2f}" for m in aggregates.top_merchants
    )
    prompt = (
        f"Month: {period_start.strftime('%B %Y')}\n"
        f"Total spend: ${aggregates.total_spend_minor / 100:,.2f}\n\n"
        f"Spend by category:\n{category_lines}\n\n"
        f"Top merchants:\n{merchant_lines}"
    )

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=150,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a short, friendly 2-3 sentence summary of this user's monthly "
                        "spending, based only on the numbers given below. Never invent a "
                        "number that isn't provided, and never mention a category or "
                        "merchant that isn't listed."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        summary = (response.choices[0].message.content or "").strip()
        return summary or None
    except Exception:
        logger.exception("OpenAI insight generation failed for period starting %s", period_start)
        return None


async def generate_insight(
    db: AsyncSession, user_id: UUID, period_start: date, period_end: date, settings: Settings
) -> Insight:
    aggregates = await compute_period_aggregates(db, user_id, period_start, period_end)
    if not aggregates.category_totals:
        raise UnprocessableError(
            "No categorized spending found for this period; nothing to summarize.",
            details={"period_start": str(period_start), "period_end": str(period_end)},
        )

    summary = await ai_summary(period_start, aggregates, settings)
    if summary is None:
        summary = template_summary(period_start, aggregates)

    insight = Insight(user_id=user_id, period_start=period_start, period_end=period_end, summary=summary)
    db.add(insight)

    event = InsightGenerated(
        user_id=user_id, period_start=period_start, period_end=period_end, summary=summary
    )
    write_outbox_event(
        db, topic=Topics.INSIGHTS_GENERATED, key=str(user_id), payload=event.model_dump(mode="json")
    )

    await db.commit()
    await db.refresh(insight)
    return insight
