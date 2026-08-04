from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span
from sqlalchemy import Engine

from app.config import Settings

SERVICE_NAME = "anomaly-service"

_tracer: trace.Tracer = trace.get_tracer(SERVICE_NAME)


def setup_tracing(settings: Settings, engine: Engine) -> None:
    """Opt-in via OTEL_EXPORTER_OTLP_ENDPOINT — see
    apps/core-api/app/core/tracing.py for the same pattern."""
    global _tracer
    if not settings.otel_exporter_otlp_endpoint:
        return

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": settings.service_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(SERVICE_NAME)

    SQLAlchemyInstrumentor().instrument(engine=engine)


@contextmanager
def continue_trace(name: str, headers: list[tuple[str, bytes]]) -> Iterator[Span]:
    """Continues the trace enrichment-service started for this message —
    see services/enrichment-service/app/tracing.py for the full
    rationale; same pattern here."""
    carrier = {k: v.decode() for k, v in headers}
    ctx = extract(carrier)
    with _tracer.start_as_current_span(name, context=ctx) as span:
        yield span


def inject_trace_headers() -> dict[str, str]:
    """Captures the currently active span's context, so an outbound
    `alerts.raised` event carries the same trace onward to
    notification-service."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier
