import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import fetch_tracked_securities, update_prices
from app.metrics import poll_errors_total, prices_updated_total
from app.provider import MarketDataProvider

logger = logging.getLogger(__name__)

# Twelve Data's free tier batches by symbol count per call — a request
# for hundreds of symbols in one call is a real API constraint, not an
# arbitrary choice; see app/investments/market_data.py's docstring in
# core-api for the same batching reasoning this mirrors.
MAX_SYMBOLS_PER_REQUEST = 100


async def poll_once(session: AsyncSession, provider: MarketDataProvider | None) -> int:
    """One full poll cycle: fetch every tracked symbol, price it, write
    updates back. Returns the number of securities updated (0 if there
    was nothing to price or the provider isn't configured — both are
    normal, not error, outcomes)."""
    if provider is None:
        logger.info("Market data provider not configured; skipping this poll cycle.")
        return 0

    tracked = await fetch_tracked_securities(session)
    if not tracked:
        logger.info("No tracked securities to price.")
        return 0

    symbols = sorted({t.symbol for t in tracked})
    now = datetime.now(UTC)
    all_prices: dict[str, int] = {}

    for start in range(0, len(symbols), MAX_SYMBOLS_PER_REQUEST):
        batch = symbols[start : start + MAX_SYMBOLS_PER_REQUEST]
        try:
            batch_prices = await provider.get_prices(batch)
        except Exception:
            # One failed batch doesn't abandon the rest — a transient
            # error pricing symbols 100-199 shouldn't also cost the
            # already-successful symbols 0-99 their update this cycle.
            poll_errors_total.inc()
            logger.exception("Failed to fetch prices for a batch of %d symbols.", len(batch))
            continue
        all_prices.update(batch_prices)

    updated = await update_prices(session, all_prices, now)
    prices_updated_total.inc(updated)
    logger.info("Priced %d/%d tracked symbols this cycle.", updated, len(symbols))
    return updated
