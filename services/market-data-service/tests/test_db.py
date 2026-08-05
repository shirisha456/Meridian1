from datetime import UTC, datetime
from uuid import uuid4

from app.db import fetch_tracked_securities, securities_table, update_prices


async def _insert_security(session, security_id, symbol, latest_price_minor=None):
    await session.execute(
        securities_table.insert().values(id=security_id, symbol=symbol, latest_price_minor=latest_price_minor)
    )
    await session.commit()


async def test_fetch_tracked_securities_returns_every_row(session_factory):
    tsla_id, aapl_id = uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_security(session, tsla_id, "TSLA")
        await _insert_security(session, aapl_id, "AAPL")

        tracked = await fetch_tracked_securities(session)

    symbols = {t.symbol for t in tracked}
    assert symbols == {"TSLA", "AAPL"}


async def test_fetch_tracked_securities_empty_when_none_exist(session_factory):
    async with session_factory() as session:
        tracked = await fetch_tracked_securities(session)
    assert tracked == []


async def test_update_prices_only_touches_matched_symbols(session_factory):
    tsla_id, aapl_id = uuid4(), uuid4()
    async with session_factory() as session:
        await _insert_security(session, tsla_id, "TSLA", latest_price_minor=1000)
        await _insert_security(session, aapl_id, "AAPL", latest_price_minor=2000)

        now = datetime.now(UTC)
        updated = await update_prices(session, {"TSLA": 26500}, now)

        rows = (await session.execute(securities_table.select())).all()

    assert updated == 1
    by_symbol = {row.symbol: row for row in rows}
    assert by_symbol["TSLA"].latest_price_minor == 26500
    # .replace(tzinfo=None) on both sides: SQLite (the test DB) doesn't
    # preserve tzinfo across a DateTime round-trip the way Postgres does
    # — a test-DB limitation, not something update_prices() gets wrong.
    assert by_symbol["TSLA"].latest_price_at.replace(tzinfo=None) == now.replace(tzinfo=None)
    # AAPL wasn't in the priced batch — left untouched, not zeroed out.
    assert by_symbol["AAPL"].latest_price_minor == 2000
    assert by_symbol["AAPL"].latest_price_at is None


async def test_update_prices_with_empty_dict_is_a_no_op(session_factory):
    async with session_factory() as session:
        await _insert_security(session, uuid4(), "TSLA", latest_price_minor=1000)
        updated = await update_prices(session, {}, datetime.now(UTC))
    assert updated == 0
