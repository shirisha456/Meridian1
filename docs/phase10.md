# Phase 10 — Grounded Monthly Insights

## Goal

A `core-api` feature, not a new service: `POST /insights/generate`
computes a user's real spending aggregates for a period and turns them
into a short natural-language summary, backed by an LLM when configured
and a deterministic template otherwise. `GET /insights/latest` returns
the most recent one. Generation also publishes `insights.generated`
through the existing outbox (ADR-0005), so `notification-service`
(built in Phase 9) fans it out live over the same WebSocket connection
alerts already use — closing the loop across Phases 7 through 10's
infrastructure with a second, independent event type.

## Architecture

```
POST /insights/generate
  → resolve_period()            defaults to the current calendar month
                                   when either bound is omitted
  → compute_period_aggregates() real SQL aggregation: total spend,
                                   spend per category (all), top 5
                                   merchants by spend — categorized,
                                   in-period expenses only
  → no categorized spending?    422 UnprocessableError — nothing to
                                   summarize, not a 200 with an empty
                                   summary
  → ai_summary()                 grounded prompt over the aggregates
                                   only, gpt-4o-mini; returns None on
                                   any failure or if unconfigured
  → template_summary()           deterministic fallback, used whenever
                                   ai_summary() returns None
  → Insight row + write_outbox_event(topic=insights.generated)
      committed together (ADR-0005)

outbox_publisher → real Redpanda topic insights.generated
  → notification-service (Phase 9, TOPIC_TO_NOTIFICATION_TYPE already
    included this topic) → Redis PUBLISH notifications:{user_id}
  → core-api WS /ws/live → browser, live, no refresh
```

## Design decisions

| Decision | Choice | Rejected alternative |
|---|---|---|
| What the model sees | Only pre-computed aggregates (total/category/merchant totals); system prompt forbids inventing numbers or entities — see [ADR-0008](adr/0008-grounded-insight-generation-with-fallback.md) | Sending raw transaction rows and letting the model compute totals — moves arithmetic into the least-verifiable part of the system |
| LLM unavailable/unconfigured | Deterministic template fallback (`template_summary()`), never a 500/503 | Failing the request when OpenAI is down — rejected, no correctness reason to couple availability to a third-party API |
| Multiple generations per period | Allowed — no uniqueness constraint on `(user_id, period_start, period_end)`; `GET /latest` returns the newest by `created_at` | A uniqueness constraint forcing "regenerate" semantics — rejected as unnecessary restriction; re-running after new transactions land is a legitimate use case |
| `created_at` ordering precision | `Insight.created_at` uses a Python-side `datetime.now(UTC)` default (microsecond resolution on both SQLite and Postgres), not only the inherited `server_default=func.now()` | Relying solely on the mixin's DB-generated default — SQLite's `CURRENT_TIMESTAMP` has only 1-second resolution, so two inserts in the same test (or, in principle, the same second in production) tie under `ORDER BY created_at DESC LIMIT 1`, making `GET /latest` non-deterministic. Caught by `test_get_latest_returns_the_most_recently_generated_insight` failing intermittently before this fix. |
| Insights as a `core-api` feature, not a new service | Synchronous, on-demand, request/response shaped — fits `core-api` directly | A dedicated `insights-service` mirroring `enrichment-service`/`anomaly-service` — those exist to consume a Kafka topic asynchronously; nothing here reacts to an event, a user action triggers it |

## The bug this phase's tests caught

`test_get_latest_returns_the_most_recently_generated_insight` generates
two insights for two different periods in quick succession and asserts
`GET /latest` returns the second one. It initially failed
intermittently: SQLite's `CURRENT_TIMESTAMP` (used by the test database,
via the inherited `TimestampMixin.created_at` `server_default=func.now()`)
only has 1-second resolution, so both rows could get an identical
timestamp, leaving `ORDER BY created_at DESC LIMIT 1` to pick arbitrarily
between them. Fixed by giving `Insight.created_at` its own Python-side
default (`datetime.now(UTC)`, microsecond resolution) in addition to the
inherited `server_default`, which the ORM insert path uses in practice.
This is the one table in the schema where a single row is ever selected
by recency (`LIMIT 1`) rather than listed, so it's the one place this
mattered enough to deviate from the shared mixin.

## Tradeoffs

- No token-usage or cost tracking for the OpenAI call — acceptable at
  the current call frequency (one per explicit user action), revisit if
  insight generation becomes higher-frequency or automatic.
- The AI summarization path (`ai_summary()`) has not been exercised
  against the real OpenAI API by this project — no key is configured in
  any test or local environment used so far. Its behavior when
  configured rests on the grounding design (ADR-0008) and the fact that
  any failure falls through to the tested, deterministic template path,
  not on having actually observed a live call succeed.
- `compute_period_aggregates()` surfaces category and merchant totals
  only — no trend-over-time, no month-over-month comparison. Both the
  template and the AI summary are limited to what this query computes.

## Verification checklist

- [x] core-api: `pytest -v` — 116 tests passing (108 from Phases 1-9 + 8
      new insights tests: 404 with nothing generated, 422 with no
      categorized spending, template-fallback content, default-period
      resolution, uncategorized/out-of-period exclusion, latest-picks-
      most-recent, outbox event written, auth required)
- [x] core-api: `alembic revision --autogenerate` produced a clean
      `insights` table (no enum columns, no downgrade fix needed this
      time); full `upgrade → downgrade base → upgrade` cycle verified
      against real Postgres
- [x] `ruff check .` — clean across core-api (including the new
      `app/insights/` package and `tests/test_insights.py`)
- [x] **Full pipeline verified against real Postgres, Redis, and
      Redpanda**, running real `core-api` and `notification-service`
      containers (not test doubles): registered a user, created a
      categorized transaction, called `POST /insights/generate` and
      confirmed the row and its exact summary via `GET /insights/latest`;
      independently consumed the real `insights.generated` Redpanda topic
      with `rpk topic consume` and confirmed the event payload; then,
      with a real WebSocket connection open via the `POST /auth/ws-ticket`
      flow, generated a second insight for a different period and
      confirmed it arrived **live over the WebSocket** — matching
      `period_start` and `summary` — within seconds, end to end through
      every hop (outbox → Redpanda → notification-service → Redis
      Pub/Sub → WebSocket).
- [ ] AI summary path (`ai_summary()` with a real `openai_api_key`
      configured) — not exercised against the live OpenAI API; only the
      template fallback has been verified end to end. Documented as an
      open gap in [ADR-0008](adr/0008-grounded-insight-generation-with-fallback.md)
      rather than claimed as tested.
