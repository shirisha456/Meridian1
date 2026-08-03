# ADR-0008: Grounded LLM summaries with a deterministic fallback

## Status

Accepted

## Context

Phase 10 adds `POST /insights/generate`: a short natural-language summary
of a user's spending for a period ("In August 2026, you spent $46.00
across 1 category..."). This is the first feature in the project that
calls an LLM directly from `core-api` (as opposed to `enrichment-service`,
which uses one for merchant-name normalization on a background pipeline
where a slow or failed call just delays enrichment, not a live request).
Two questions this ADR answers: what is the model allowed to see, and
what happens when the call is unavailable, slow, or wrong.

## Decision

1. **Grounded, not free-form.** `compute_period_aggregates()` runs the
   real aggregation query first (total spend, per-category totals, top-5
   merchants) and only those pre-computed numbers are put in the prompt —
   never raw transaction rows. The system prompt explicitly instructs the
   model not to invent a number or mention a category/merchant that
   wasn't listed. This bounds what a hallucination can look like: the
   model can misdescribe or omit real numbers, but it cannot fabricate a
   transaction that never happened.
2. **Deterministic template fallback, always available.** `ai_summary()`
   never raises — any exception (missing API key, network failure, rate
   limit, empty response) is caught and logged, and `generate_insight()`
   falls back to `template_summary()`, a pure string-formatting function
   over the same aggregates with no external call. The feature is never
   fully down because of OpenAI; it just becomes less polished.
3. **`openai_api_key` is optional configuration**, not a hard dependency
   — unset in development/test by default, degrading straight to the
   template path with no error.

## Alternatives considered

- **Fail the request (503) if the LLM call fails** — rejected. Unlike
  Redis (ADR-0002), there's no correctness reason to couple insight
  generation's availability to a third-party API's uptime; the template
  summary is a complete, accurate answer to "what did I spend," just
  less conversational.
- **Send raw transactions to the model and let it compute totals** —
  rejected. Cheaper to prompt, but moves the arithmetic into the
  least-verifiable part of the system; a miscounted total would look
  exactly as plausible as a correct one. Computing aggregates in SQL and
  only handing over the results keeps the numbers a place I've actually
  tested (`test_generate_excludes_uncategorized_and_out_of_period_transactions`,
  `test_generate_uses_template_fallback_when_openai_not_configured`).
- **A separate insights-service**, mirroring `enrichment-service`/
  `anomaly-service` — rejected for this phase. Those services exist to
  consume a Kafka topic asynchronously; insight generation is a
  synchronous, on-demand, per-request action (`POST /insights/generate`
  called by a user action, not a background reaction to an event), which
  fits the request/response shape of `core-api` rather than a consumer
  loop. `InsightGenerated` is still published to Kafka afterward, for
  `notification-service` to fan out live — that part follows the
  existing outbox pattern (ADR-0005) unchanged.

## Consequences

- Insight quality is capped by what the aggregation query surfaces
  (category and merchant totals only, no trend-over-time or
  merchant-category correlation) — matches what the template fallback
  can also express, since both paths are grounded in the same
  `PeriodAggregates`.
- Two summaries for the same numbers can read differently between
  requests, or between the AI path and the template path (e.g. after an
  API key is added or removed) — expected and acceptable for a
  natural-language summary, not a reason to cache/pin wording.
- No token-usage or cost tracking exists yet. Not needed at current
  scale (one call per explicit `POST /generate`, not per page load), but
  would need addressing before this became a high-frequency or
  auto-triggered feature.

## Validation

`apps/core-api/tests/test_insights.py`:
`test_generate_uses_template_fallback_when_openai_not_configured` proves
the fallback path produces a correct, specific summary
(`"January 2026"`, `"$46.00"`, `"Food & Dining"` all present) with no API
key configured — the only path actually exercised in CI and in this
project's own manual verification, since no OpenAI key is provisioned in
any test or local environment. The AI path (`ai_summary()`) has not been
exercised against the real OpenAI API in this project; its correctness
rests on the grounding design above and the fact that any failure there
falls through to the tested template path, not on having actually run
a live call.
