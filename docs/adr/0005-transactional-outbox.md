# ADR-0005: Transactional outbox instead of a dual write to Kafka

## Status

Accepted

## Context

Creating a transaction needs to both persist it in Postgres and (when
uncategorized) tell the future enrichment consumer it exists. Writing to
Postgres and publishing to Kafka are two separate systems with no shared
transaction — if the code committed the Postgres row and then called the
Kafka producer as two independent steps, a crash between them (or a
Kafka-side failure) leaves the transaction persisted with no event ever
published, silently un-enriched forever, with no error surfaced to
anyone.

## Decision

Business writes and their corresponding events are written in the same
Postgres transaction: `app/core/outbox.py::write_outbox_event()` just
does `db.add(OutboxEvent(...))` with no commit, and callers (e.g.
`app/transactions/router.py::create_transaction`) commit the business
row and the outbox row together. A separate background loop
(`app/core/outbox_publisher.py`) polls for unpublished rows every 3
seconds and publishes them to Kafka, marking each row published only
after a confirmed send.

## Alternatives considered

- **Dual write** (commit to Postgres, then separately call the Kafka
  producer) — rejected for the reason in Context: a failure between the
  two steps loses the event with no trace it was supposed to exist.
- **Change Data Capture** (e.g. Debezium reading the Postgres WAL) —
  a real, common alternative to the outbox pattern that avoids the
  polling delay and the extra table entirely. Rejected for this
  project's scale: it requires running and operating a CDC connector
  (Debezium + Kafka Connect) as additional infrastructure, which is
  disproportionate to a personal-scale app publishing a few events per
  transaction. The outbox table is a few lines of code and one extra
  table; CDC is a genuinely different infrastructure commitment.

## Consequences

- At-least-once delivery, not exactly-once: see ADR-0006 for exactly how
  the publish loop avoids marking a row published before Kafka actually
  confirms it, and the specific (narrow, documented, and only
  duplicate-risking, never loss-risking) race that remains.
- Every future write path that needs to publish an event follows the
  same pattern — add the business row and an `OutboxEvent` row to the
  same session, commit once. No new infrastructure needed as more event
  types are added in Phase 8+.
- A 3-second polling interval means up to ~3 seconds of latency between
  a transaction being created and its event reaching Kafka — acceptable
  for background categorization, not appropriate if this pattern were
  ever reused for something latency-sensitive.

## Validation

`apps/core-api/tests/test_outbox.py` covers: a row written via
`write_outbox_event` is not visible as published until
`publish_pending_outbox_events` runs; a successful publish marks it
published; a producer failure on one row leaves it unpublished (retried
next cycle) without blocking other rows in the same batch. Verified
end-to-end against a real Redpanda broker in this phase's manual
verification (`docs/phase7.md`), not just against a fake producer.
