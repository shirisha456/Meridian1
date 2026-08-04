from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import Engine

from app.core.config import Settings


def setup_tracing(app: FastAPI, engine: Engine, settings: Settings) -> None:
    """Tracing is opt-in via OTEL_EXPORTER_OTLP_ENDPOINT — unset in a plain
    `pytest` run or a laptop without the observability stack running, so
    this is a no-op rather than a hard dependency."""
    if not settings.otel_exporter_otlp_endpoint:
        return

    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    # Covers both the Plaid client (app/institutions/plaid_client.py, a
    # hand-written httpx client — see ADR-0007) and the OpenAI SDK, which
    # uses httpx internally — neither gets its own manual span, this is
    # the only tracing either outbound call has.
    HTTPXClientInstrumentor().instrument()


def capture_trace_headers() -> dict[str, str]:
    """Kafka has no built-in trace propagation the way HTTP middleware
    does — the W3C traceparent has to be carried in message headers by
    hand so a consumer can continue the same trace. Captured at outbox
    *write* time (while the original request's span is still active),
    not at publish time (the background publisher loop runs on its own
    schedule with no request span active) — see
    app/core/outbox.py::write_outbox_event and docs/phase12.md."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier
