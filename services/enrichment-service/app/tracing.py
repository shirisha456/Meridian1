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

SERVICE_NAME = "enrichment-service"

_tracer: trace.Tracer = trace.get_tracer(SERVICE_NAME)


def setup_tracing(settings: Settings, engine: Engine) -> None:
    """Opt-in via OTEL_EXPORTER_OTLP_ENDPOINT — a no-op in tests or a
    laptop without the observability stack running. See
    apps/core-api/app/core/tracing.py for the same pattern there."""
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

    # core-api's FastAPI/httpx auto-instrumentation has no equivalent here
    # (this is a plain Kafka consumer loop, no HTTP framework) — SQLAlchemy
    # is the one auto-instrumentable thing this service has.
    SQLAlchemyInstrumentor().instrument(engine=engine)


@contextmanager
def continue_trace(name: str, headers: list[tuple[str, bytes]]) -> Iterator[Span]:
    """Kafka has no built-in trace propagation the way HTTP middleware
    does — the producer side hand-carries a W3C traceparent in message
    headers (see apps/core-api/app/core/tracing.py::capture_trace_headers,
    and inject_trace_headers below for this service's own outbound
    publish), and this extracts it back out so the whole
    ingest → enrich → (anomaly-detect) → notify pipeline shows up as one
    connected trace in Tempo rather than four disconnected ones."""
    carrier = {k: v.decode() for k, v in headers}
    ctx = extract(carrier)
    with _tracer.start_as_current_span(name, context=ctx) as span:
        yield span


def inject_trace_headers() -> dict[str, str]:
    """Captures the *currently active* span's context — call this from
    inside the `continue_trace` block wrapping message processing, so the
    outbound `transactions.enriched` event carries the same trace onward
    to anomaly-service."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier
