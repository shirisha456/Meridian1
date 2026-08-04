from prometheus_client import Counter

processed_total = Counter(
    "meridian_anomaly_processed_total", "transactions.enriched messages successfully processed"
)
alerts_raised_total = Counter(
    "meridian_anomaly_alerts_raised_total", "Alerts raised, by rule", ["alert_type"]
)
errors_total = Counter(
    "meridian_anomaly_errors_total", "transactions.enriched messages that failed processing"
)
