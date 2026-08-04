# Phase 12 — Observability

## Goal

Distributed tracing (OpenTelemetry → Tempo), metrics (Prometheus,
scraped from every service), and structured logs (Loki, via Promtail) —
wired so the four-service event pipeline built across Phases 7–9 is
actually *visible* as one connected system, not four services whose
logs a human correlates by hand. Studied against the reference
implementation's own observability stack
(`C:\Users\Shirisha\meridian1\observability\`) and its OTel wiring in
`apps/core-api` and each worker, then rebuilt with the specific gaps
that research surfaced fixed.

## Gaps in the reference, fixed in this rebuild

1. **Trace-log correlation didn't actually work.** The reference wired a
   Tempo→Loki `tracesToLogsV2` datasource link in Grafana, but no
   service ever put a `trace_id` into a log line (plain
   `logging.basicConfig` text format, no OTel logging integration
   anywhere) — the link had nothing to filter on. This rebuild's
   `configure_logging()` (one per service — `apps/core-api/app/core/logging.py`
   and each worker's `app/logging_config.py`) emits structured JSON with
   a `TraceContextFilter` that injects `trace_id`/`span_id` onto every
   log record while a span is active, and Promtail's pipeline
   (`observability/promtail/promtail-config.yml`) parses that JSON and
   attaches `trace_id`/`span_id` as Loki *structured metadata* (not
   labels — see the tradeoffs section on why). **Verified working**, not
   assumed — see the checklist below.
2. **No SQLAlchemy instrumentation on `enrichment-service`/`anomaly-service`**,
   despite both using it for DB access, even though `core-api` had it.
   Both now call `SQLAlchemyInstrumentor().instrument(engine=...)` in
   their own `app/tracing.py`, same as core-api.
3. **`notification-service` had no tracing at all** — no OTel packages,
   no `OTEL_EXPORTER_OTLP_ENDPOINT`. It's the terminal hop of the
   pipeline (Kafka → Redis Pub/Sub, nothing published onward), so it
   doesn't need the SQLAlchemy or outbound-propagation pieces the other
   two have, but it now extracts and continues the incoming trace
   (`continue_trace` in `services/notification-service/app/tracing.py`)
   so the trace doesn't dead-end one hop early.
4. **No `/health` on any of the four workers** was already fixed before
   this phase (Phase 9's `app/health.py`, a stdlib `http.server`). This
   phase extends that *same* server to also serve `/metrics`
   (`prometheus_client.generate_latest()`) — one port doing both jobs,
   rather than the reference's two separate mechanisms (a bare
   `prometheus_client.start_http_server` on its own port, with no health
   endpoint at all next to it).
5. **No panels for `anomaly-service`'s or `notification-service`'s own
   counters** in the reference's Grafana dashboard, despite both being
   collected. Both get real panels now
   (`observability/grafana/dashboards/meridian-overview.json`).
6. **Outbound third-party calls (OpenAI, Plaid) were untraced.** Both go
   through `httpx` (`core-api`'s Plaid client is hand-written on top of
   it — see ADR-0007 — and the OpenAI SDK uses `httpx` internally), so
   `HTTPXClientInstrumentor().instrument()` in `core-api`'s
   `app/core/tracing.py` covers both for free, without a manual span
   around either call site.

## Architecture

```
core-api (FastAPI)
  Instrumentator().instrument(app).expose(app)   → GET /metrics, always on
  setup_tracing(app, engine.sync_engine, settings) → opt-in, FastAPI +
    SQLAlchemy + httpx auto-instrumentation, OTLP/http → tempo:4318
  write_outbox_event() captures the active span's W3C traceparent into
    OutboxEvent.trace_headers (new column, Phase 12 migration)
  outbox_publisher reads trace_headers back out onto the Kafka message's
    own headers when it actually publishes

enrichment-service / anomaly-service / notification-service
  app/tracing.py: continue_trace(name, message.headers) extracts the
    traceparent and opens a child span for the whole message-processing
    call; inject_trace_headers() (enrichment, anomaly — the two that
    publish onward) captures *that* span's context for their own
    outbound Kafka message
  app/logging_config.py: same JSON + TraceContextFilter pattern as
    core-api
  app/health.py: one http.server, /health + /metrics
  app/metrics.py: prometheus_client Counters — processed_total/errors_total
    everywhere, alerts_raised_total{alert_type} (anomaly),
    forwarded_total{type} (notification)

observability/
  prometheus/prometheus.yml   scrapes core-api:8000 and each worker's
                                 health-server port (8080/8081/8082)
  loki/loki-config.yml        filesystem-backed, allow_structured_metadata: true
  promtail/promtail-config.yml docker_sd_configs + a json pipeline stage
                                 parsing every service's structured logs,
                                 promoting level to a label and
                                 trace_id/span_id to structured metadata
  tempo/tempo.yml             OTLP receiver (http+grpc), local block storage
  grafana/                    Prometheus (default) + Loki + Tempo
                                 datasources provisioned, Tempo→Loki
                                 tracesToLogsV2 wired with filterByTraceID,
                                 one dashboard (meridian-overview.json)
```

## Design decisions

| Decision | Choice | Rejected alternative |
|---|---|---|
| Collector or no | No OTel Collector — every service exports OTLP directly to Tempo | See [ADR-0010](adr/0010-direct-otlp-export-no-collector.md) |
| Trace-log correlation | `trace_id`/`span_id` injected into structured JSON logs via a logging Filter reading the active OTel span, parsed back out by Promtail into Loki structured metadata | The reference's approach: wire the Grafana datasource link and never actually put a trace_id in a log line — a link with nothing to correlate |
| `trace_id`/`span_id` as Loki labels vs. structured metadata | Structured metadata | Labels — a Loki label is an index dimension; trace_id has one distinct value per request, which would blow up cardinality. `level` (a handful of distinct values) is promoted to a label instead; trace_id/span_id use Loki 3.x's structured metadata, filterable via `\| trace_id="..."` without being indexed |
| Health + metrics endpoint | One `http.server` per worker serving both `/health` and `/metrics` | The reference's two separate mechanisms (bare `prometheus_client.start_http_server`, no health endpoint alongside it) |
| JSON logs: when | Whenever stdout isn't a TTY (`sys.stdout.isatty()`), not keyed off `environment == "development"` alone | `environment`-only — `docker compose up` also runs with `ENVIRONMENT=development`, but its stdout is captured by the Docker daemon for Promtail, not read by a human directly, and needs the structured form regardless |
| Trace propagation across Kafka | Capture the W3C traceparent at outbox-*write* time (while the original request's span is still active), store it on the outbox row, inject it as Kafka message headers at *publish* time | Injecting "current" context at publish time — the background outbox publisher loop runs on its own 3-second schedule with no request span active by then; there'd be nothing real to inject |

## Tradeoffs

- No OTel Collector (see ADR-0010) — no tail sampling, no PII scrubbing
  layer, no multi-backend fan-out. Not needed at this scale; revisit if
  any of those become real requirements.
- No alerting rules (Prometheus `rule_files`/Alertmanager) — matches the
  reference; this phase is observability *visibility*, not on-call
  paging.
- Grafana runs with anonymous Admin access
  (`GF_AUTH_ANONYMOUS_ENABLED=true`) — acceptable for a local-only
  Compose stack, explicitly not a setting to carry into anything shared
  or internet-reachable.
- Log retention is 7 days (Loki compactor) and traces 24 hours (Tempo
  compactor) — local-dev-appropriate defaults, not a durability
  guarantee, matching the reference.
- Metrics use `prometheus_client` directly (Counters/Gauges), not the
  OTel Metrics SDK — traces go through OpenTelemetry, metrics through
  Prometheus's own client library. A deliberate hybrid (matches the
  reference), not a gap: OTel's metrics API would ultimately export to
  the same Prometheus scrape-based model via an exporter, so this skips
  a layer without losing anything at this scale.

## Verification checklist

- [x] core-api: `pytest -v` — 116 tests passing (including updated
      `FakeKafkaProducer`/outbox tests reflecting the new `headers`
      parameter)
- [x] enrichment-service: `pytest -v` — 24 passing; anomaly-service — 17
      passing; notification-service — 5 passing; libs/events — 6 passing
      (168 total across all five packages)
- [x] `ruff check .` — clean across all four Python packages touched
      this phase
- [x] core-api: `alembic revision --autogenerate` produced a clean
      `outbox_events.trace_headers` column (JSON, `server_default='{}'`
      so it's safe to add NOT NULL against a table with existing rows);
      full `upgrade → downgrade base → upgrade` cycle verified against
      real Postgres
- [x] **Full stack verified against real infrastructure** — brought up
      Postgres, Redis, Redpanda, all four app services, and all five
      observability services (Tempo, Prometheus, Loki, Promtail,
      Grafana) via `docker compose up`; confirmed all four app services'
      structured JSON logs include `trace_id`/`span_id` on every request
      (confirmed directly in container logs, not just code review)
- [x] **Prometheus**: all four scrape targets (`core-api`,
      `enrichment-service`, `anomaly-service`, `notification-service`)
      report `health: "up"` via `/api/v1/targets`
- [x] **Distributed tracing, end-to-end, real data**: registered a user,
      created an account, posted the same transaction twice (to trigger
      anomaly-service's duplicate-charge rule) through the real running
      `core-api`. Confirmed via `GET /api/v1/alerts` that the alert was
      actually raised, then fetched the resulting trace directly from
      Tempo's `/api/traces/{traceID}` API and confirmed it contains, as
      correctly nested child spans within *one* trace (not four separate
      ones): `POST /api/v1/transactions` (core-api, with its own
      SQLAlchemy INSERT spans) → `enrichment-service.process` (with its
      own SQLAlchemy spans) → `anomaly-service.process` (with its own
      SQLAlchemy spans, including the alert INSERT) →
      `notification-service.process`. This is the single most important
      thing this phase had to get right and it's confirmed working with
      real trace data, not asserted from reading the code.
- [x] **Trace-log correlation, real data**: queried Loki (via Grafana's
      datasource proxy, since Loki has no host-published port — same as
      the reference) for `{service=~".+"} | trace_id="<the trace ID
      above>"` and got back the actual log lines from `core-api`
      (`"POST /api/v1/transactions HTTP/1.1" 201`) and `anomaly-service`
      (`"Raised 1 alert(s) from offset 1."`), both correctly tagged with
      that exact trace_id as structured metadata. The reference's
      equivalent Grafana link had nothing to correlate; this one does.
- [x] **Grafana dashboard**: fetched via
      `GET /api/dashboards/uid/meridian-overview` and confirmed all 9
      panels are provisioned; queried three of the custom PromQL metrics
      directly through Grafana's Prometheus datasource proxy
      (`meridian_outbox_pending`, `meridian_transactions_created_total`,
      `meridian_anomaly_alerts_raised_total`) and confirmed they return
      real values reflecting the test traffic above (the
      `duplicate_charge` alert counter reads `1`, matching the one alert
      actually raised).
- [ ] Not verified: Grafana's Tempo→Loki "click a span, jump to its
      logs" UI flow was confirmed to have real, correlated data
      available (the query above proves the data itself is right), but
      the actual click-through UI interaction was not driven through a
      browser this phase — a reasonable, lower-risk gap given the
      underlying data was directly confirmed correct via the same API
      Grafana's UI calls.
