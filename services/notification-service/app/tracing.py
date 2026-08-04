from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from app.config import Settings

SERVICE_NAME = "notification-service"

_tracer: trace.Tracer = trace.get_tracer(SERVICE_NAME)


def setup_tracing(settings: Settings) -> None:
    """Opt-in via OTEL_EXPORTER_OTLP_ENDPOINT — see
    apps/core-api/app/core/tracing.py for the same pattern. No
    SQLAlchemyInstrumentor here (unlike enrichment/anomaly-service) — this
    service has no database access, only Kafka in and Redis Pub/Sub out."""
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


@contextmanager
def continue_trace(name: str, headers: list[tuple[str, bytes]]) -> Iterator[Span]:
    """Continues the trace started upstream (core-api on write, carried
    through enrichment-service/anomaly-service) — this is the terminal
    hop, nothing is published onward from here (Redis Pub/Sub delivery to
    a browser isn't part of this backend trace)."""
    carrier = {k: v.decode() for k, v in headers}
    ctx = extract(carrier)
    with _tracer.start_as_current_span(name, context=ctx) as span:
        yield span
