from typing import Protocol

import httpx


class MarketDataNotConfigured(RuntimeError):
    pass


class MarketDataProvider(Protocol):
    async def get_prices(self, symbols: list[str]) -> dict[str, int]:
        """Returns {symbol: price_minor} for whichever symbols the
        provider could price — a symbol it doesn't recognize is simply
        absent from the result, not an error for the whole batch."""
        ...


class TwelveDataProvider:
    """Deliberately duplicated from apps/core-api/app/investments/
    market_data.py's TwelveDataProvider rather than shared via a common
    lib — this service and core-api are independent deployables per
    ADR-0007, and this client is small enough that a shared package
    would cost more in cross-service coupling than it saves in avoided
    duplication (unlike libs/events, which exists specifically because
    the *event schema* must be identical on both sides of a Kafka topic;
    there is no such shared-contract requirement here)."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url

    async def get_prices(self, symbols: list[str]) -> dict[str, int]:
        if not symbols:
            return {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._base_url}/price",
                params={"symbol": ",".join(symbols), "apikey": self._api_key},
            )
            response.raise_for_status()
            payload = response.json()

        # Twelve Data returns a flat {"price": "..."} object for a single
        # symbol and {SYMBOL: {"price": "..."}, ...} for multiple —
        # normalize both shapes to the same dict-of-dicts form.
        if len(symbols) == 1:
            payload = {symbols[0]: payload}

        prices: dict[str, int] = {}
        for symbol, entry in payload.items():
            if isinstance(entry, dict) and "price" in entry:
                prices[symbol] = round(float(entry["price"]) * 100)
        return prices


def get_provider(api_key: str, base_url: str) -> MarketDataProvider | None:
    if not api_key:
        return None
    return TwelveDataProvider(api_key, base_url)
