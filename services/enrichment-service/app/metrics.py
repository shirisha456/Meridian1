from prometheus_client import Counter

processed_total = Counter(
    "meridian_enrichment_processed_total", "transactions.ingested messages successfully processed"
)
errors_total = Counter(
    "meridian_enrichment_errors_total", "transactions.ingested messages that failed processing"
)
