import json
import logging
import sys
from datetime import UTC, datetime

from opentelemetry import trace

_RESERVED_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)


class JsonFormatter(logging.Formatter):
    """Structured JSON logs — one object per line, ready for Loki. Same
    formatter as the other three services' app/logging_config.py."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extras = {
            key: value for key, value in record.__dict__.items() if key not in _RESERVED_LOG_RECORD_ATTRS
        }
        if extras:
            payload.update(extras)

        return json.dumps(payload, default=str)


class TraceContextFilter(logging.Filter):
    """Injects trace_id/span_id into every log record emitted while a
    span is active, so a log line and the trace it happened inside can be
    correlated in Grafana."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        context = span.get_span_context()
        if context.is_valid:
            record.trace_id = format(context.trace_id, "032x")
            record.span_id = format(context.span_id, "016x")
        return True


def configure_logging(level: str, environment: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if environment == "development" and sys.stdout.isatty():
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())

    handler.addFilter(TraceContextFilter())
    root.addHandler(handler)
