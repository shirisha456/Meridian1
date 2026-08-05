from uuid import uuid4

from app.db import securities_table
from app.poller import poll_once


async def _insert_security(session, security_id, symbol):
    await session.execute(securities_table.insert().values(id=security_id, symbol=symbol))
    await session.commit()


class FakeProvider:
    def __init__(self, prices: dict[str, int], *, fail_symbols: set[str] | None = None) -> None:
        self._prices = prices
        self._fail_symbols = fail_symbols or set()

    async def get_prices(self, symbols: list[str]) -> dict[str, int]:
        if set(symbols) & self._fail_symbols:
            raise RuntimeError("provider unavailable for this batch")
        return {symbol: self._prices[symbol] for symbol in symbols if symbol in self._prices}


async def test_poll_once_returns_zero_when_provider_not_configured(session_factory):
    async with session_factory() as session:
        await _insert_security(session, uuid4(), "TSLA")
        updated = await poll_once(session, provider=None)
    assert updated == 0


async def test_poll_once_returns_zero_when_nothing_tracked(session_factory):
    async with session_factory() as session:
        updated = await poll_once(session, provider=FakeProvider({"TSLA": 26500}))
    assert updated == 0


async def test_poll_once_prices_every_tracked_symbol(session_factory):
    async with session_factory() as session:
        await _insert_security(session, uuid4(), "TSLA")
        await _insert_security(session, uuid4(), "AAPL")

        updated = await poll_once(session, provider=FakeProvider({"TSLA": 26500, "AAPL": 23100}))

        rows = (await session.execute(securities_table.select())).all()

    assert updated == 2
    by_symbol = {row.symbol: row.latest_price_minor for row in rows}
    assert by_symbol == {"TSLA": 26500, "AAPL": 23100}


async def test_poll_once_leaves_unpriced_symbols_untouched(session_factory):
    async with session_factory() as session:
        await _insert_security(session, uuid4(), "TSLA")
        await _insert_security(session, uuid4(), "DELISTED")

        updated = await poll_once(session, provider=FakeProvider({"TSLA": 26500}))

    assert updated == 1


async def test_poll_once_survives_a_batch_that_raises(session_factory):
    """A batching provider error for symbols 100-199 shouldn't cost
    symbols 0-99 their update — proven directly by making MAX_SYMBOLS_
    PER_REQUEST-many symbols split across two batches, one of which
    fails."""
    import app.poller as poller_module

    original_batch_size = poller_module.MAX_SYMBOLS_PER_REQUEST
    poller_module.MAX_SYMBOLS_PER_REQUEST = 1
    try:
        async with session_factory() as session:
            await _insert_security(session, uuid4(), "GOOD")
            await _insert_security(session, uuid4(), "BAD")

            updated = await poll_once(
                session, provider=FakeProvider({"GOOD": 100, "BAD": 200}, fail_symbols={"BAD"})
            )

            rows = (await session.execute(securities_table.select())).all()
    finally:
        poller_module.MAX_SYMBOLS_PER_REQUEST = original_batch_size

    assert updated == 1
    by_symbol = {row.symbol: row.latest_price_minor for row in rows}
    assert by_symbol["GOOD"] == 100
    assert by_symbol["BAD"] is None
