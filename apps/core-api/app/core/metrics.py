from prometheus_client import Counter, Gauge

transactions_created_total = Counter(
    "meridian_transactions_created_total", "Transactions created via the API", ["source"]
)

outbox_pending = Gauge(
    "meridian_outbox_pending", "Unpublished rows currently sitting in the outbox table"
)
