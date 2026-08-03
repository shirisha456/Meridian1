from dataclasses import dataclass
from uuid import UUID

from meridian_events import TransactionEnriched
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import find_duplicate_charge, get_category_spend_stats, get_previous_amount_for_merchant

SPEND_SPIKE_MULTIPLE = 3.0
SPEND_SPIKE_MIN_PRIOR_TRANSACTIONS = 5
PRICE_INCREASE_THRESHOLD = 1.05  # 5% higher than the previous occurrence


@dataclass
class AlertCandidate:
    alert_type: str
    severity: str
    title: str
    detail: str
    related_transaction_id: UUID | None


async def detect_duplicate_charge(
    session: AsyncSession, event: TransactionEnriched
) -> AlertCandidate | None:
    duplicate_of = await find_duplicate_charge(
        session, event.account_id, event.merchant_name, event.amount_minor, event.txn_date, event.transaction_id
    )
    if duplicate_of is None:
        return None
    return AlertCandidate(
        alert_type="duplicate_charge",
        severity="warning",
        title=f"Possible duplicate charge at {event.merchant_name}",
        detail=(
            f"Another transaction for the same amount at {event.merchant_name} "
            f"was recorded within a day of this one."
        ),
        related_transaction_id=event.transaction_id,
    )


async def detect_spend_spike(
    session: AsyncSession, event: TransactionEnriched
) -> AlertCandidate | None:
    # Only expenses (negative amounts) in a known category can spike
    # against a category average.
    if event.category_id is None or event.amount_minor >= 0:
        return None

    stats = await get_category_spend_stats(session, event.user_id, event.category_id, event.txn_date)
    if stats.prior_count < SPEND_SPIKE_MIN_PRIOR_TRANSACTIONS or stats.average_abs_amount_minor <= 0:
        return None

    if abs(event.amount_minor) <= stats.average_abs_amount_minor * SPEND_SPIKE_MULTIPLE:
        return None

    return AlertCandidate(
        alert_type="spend_spike",
        severity="warning",
        title=f"Unusually high spend at {event.merchant_name}",
        detail=(
            f"This {abs(event.amount_minor) / 100:.2f} {event.currency} charge is more than "
            f"{SPEND_SPIKE_MULTIPLE:.0f}x this category's 90-day average "
            f"({stats.average_abs_amount_minor / 100:.2f} {event.currency})."
        ),
        related_transaction_id=event.transaction_id,
    )


async def detect_subscription_price_increase(
    session: AsyncSession, event: TransactionEnriched
) -> AlertCandidate | None:
    if not event.is_recurring or event.amount_minor >= 0:
        return None

    previous_amount = await get_previous_amount_for_merchant(
        session, event.account_id, event.merchant_name, event.txn_date, event.transaction_id
    )
    if previous_amount is None or previous_amount >= 0:
        return None

    if abs(event.amount_minor) <= abs(previous_amount) * PRICE_INCREASE_THRESHOLD:
        return None

    return AlertCandidate(
        alert_type="subscription_price_increase",
        severity="info",
        title=f"{event.merchant_name} price increased",
        detail=(
            f"{event.merchant_name} charged {abs(event.amount_minor) / 100:.2f} {event.currency}, "
            f"up from {abs(previous_amount) / 100:.2f} {event.currency} last time."
        ),
        related_transaction_id=event.transaction_id,
    )


ALL_RULES = [detect_duplicate_charge, detect_spend_spike, detect_subscription_price_increase]
