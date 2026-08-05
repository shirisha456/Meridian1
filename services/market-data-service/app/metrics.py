from prometheus_client import Counter

prices_updated_total = Counter(
    "meridian_market_data_prices_updated_total", "Securities whose latest_price_minor was updated"
)
poll_errors_total = Counter(
    "meridian_market_data_poll_errors_total", "Provider batches that failed to fetch during a poll cycle"
)
