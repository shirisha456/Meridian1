from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span
from sqlalchemy import Engine

from app.config import Settings

SERVICE_NAME = "market-data-service"

_tracer: trace.Tracer = trace.get_tracer(SERVICE_NAME)


def setup_tracing(settings: Settings, engine: Engine) -> None:
    """Opt-in via OTEL_EXPORTER_OTLP_ENDPOINT — a no-op in tests or a
    laptop without the observability stack running. Same pattern as the
    other three services' app/tracing.py.

    Simpler than enrichment-service's: this poller has no inbound Kafka
    message to extract a traceparent from and no downstream event to
    carry one onward (this service doesn't produce to Kafka — see
    ADR-0014 for why) — each poll cycle just starts its own root span
    rather than continuing someone else's trace.
    """
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
def poll_cycle_span(name: str) -> Iterator[Span]:
    with _tracer.start_as_current_span(name) as span:
        yield span
