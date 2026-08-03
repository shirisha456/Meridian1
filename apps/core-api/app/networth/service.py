from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account, AccountType
from app.networth.models import NetWorthSnapshot

LIABILITY_TYPES = {AccountType.credit, AccountType.loan}


async def recompute_snapshot(db: AsyncSession, user_id: UUID) -> NetWorthSnapshot:
    accounts = await db.scalars(select(Account).where(Account.user_id == user_id))

    assets_minor = 0
    liabilities_minor = 0
    for account in accounts:
        if account.type in LIABILITY_TYPES:
            # Classified by account type, not by the sign of
            # current_balance_minor: a manually-entered credit/loan
            # balance is naturally "how much I owe," which most people
            # enter as a positive number even though the rest of the
            # schema's convention is negative-for-liability. abs() here
            # makes net worth correct either way, rather than silently
            # depending on the caller following the sign convention.
            liabilities_minor += abs(account.current_balance_minor)
        else:
            assets_minor += account.current_balance_minor

    net_worth_minor = assets_minor - liabilities_minor
    # UTC, not server-local time — consistent with TimestampMixin
    # elsewhere, and avoids the snapshot date silently depending on the
    # deploy host's timezone.
    today = datetime.now(UTC).date()

    existing = await db.scalar(
        select(NetWorthSnapshot).where(
            NetWorthSnapshot.user_id == user_id, NetWorthSnapshot.snapshot_date == today
        )
    )
    if existing is not None:
        existing.assets_minor = assets_minor
        existing.liabilities_minor = liabilities_minor
        existing.net_worth_minor = net_worth_minor
        await db.commit()
        await db.refresh(existing)
        return existing

    snapshot = NetWorthSnapshot(
        user_id=user_id,
        snapshot_date=today,
        assets_minor=assets_minor,
        liabilities_minor=liabilities_minor,
        net_worth_minor=net_worth_minor,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
