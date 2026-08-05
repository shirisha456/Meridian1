from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Column, DateTime, MetaData, String, Table, Uuid, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# This service does not own this schema and never runs migrations
# against it — apps/core-api's Alembic migrations are the single source
# of truth for the `securities` table. Only the columns this service
# actually reads or writes are declared, deliberately, as a
# minimal-surface contract against a schema owned elsewhere (ADR-0007,
# same pattern as services/enrichment-service/app/db.py).
metadata = MetaData()

securities_table = Table(
    "securities",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("symbol", String),
    Column("latest_price_minor", BigInteger, nullable=True),
    Column("latest_price_at", DateTime(timezone=True), nullable=True),
)


@dataclass
class TrackedSecurity:
    id: UUID
    symbol: str


async def fetch_tracked_securities(session: AsyncSession) -> list[TrackedSecurity]:
    """Every row in `securities` is already "tracked" by construction —
    apps/core-api only ever creates one via get_or_create_security when a
    holding or watchlist item first references that symbol (see
    app/investments/router.py there). There is no separate opt-in step;
    a security with nobody holding or watching it anymore just stops
    mattering, but this service has no way to know that distinction and
    doesn't need to — pricing a handful of extra symbols each cycle costs
    nothing a user-facing request would notice."""
    rows = await session.execute(select(securities_table.c.id, securities_table.c.symbol))
    return [TrackedSecurity(id=row.id, symbol=row.symbol) for row in rows]


async def update_prices(session: AsyncSession, prices_by_symbol: dict[str, int], now: datetime) -> int:
    """Updates every tracked security whose symbol the provider actually
    returned a price for. Returns the number of rows updated so the
    caller can log/metric it. A symbol the provider doesn't recognize is
    simply left with its previous latest_price_minor rather than being
    zeroed out — a stale price is more useful than no price."""
    if not prices_by_symbol:
        return 0

    updated = 0
    for symbol, price_minor in prices_by_symbol.items():
        result = await session.execute(
            update(securities_table)
            .where(securities_table.c.symbol == symbol)
            .values(latest_price_minor=price_minor, latest_price_at=now)
        )
        updated += result.rowcount
    await session.commit()
    return updated
