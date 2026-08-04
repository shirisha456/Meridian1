from prometheus_client import Counter

forwarded_total = Counter(
    "meridian_notification_forwarded_total", "Notifications published to Redis Pub/Sub, by type", ["type"]
)
errors_total = Counter(
    "meridian_notification_errors_total", "Messages that failed processing"
)
