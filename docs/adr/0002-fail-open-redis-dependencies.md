# ADR-0002: Redis-backed features fail open, not closed

## Status

Accepted

## Context

Redis backs several features in this app that aren't the source of truth
for anything: idempotency-key caching (Phase 3), and later, response
caching and rate limiting. Postgres is always the source of truth; Redis
is an optimization/safety-net layer on top of it. The question this ADR
answers: when Redis is unreachable, should the request that depends on it
fail, or proceed as if the Redis-backed feature simply wasn't there?

## Decision

Every Redis-backed feature fails open: a `RedisError` is caught, logged
as a warning, and the code proceeds as though the cache had missed (for
idempotency: "no cached response found," i.e. process the request
normally) rather than propagating as a 500 or 503 to the client.

## Alternatives considered

- **Fail closed** (surface a 503 or 500 if Redis is unreachable) — the
  correct choice when the Redis-backed behavior is itself a correctness
  guarantee the caller depends on (e.g. a distributed lock preventing a
  double-spend). It is not the right choice here: an idempotency-key
  cache miss just means a client retry might create a second manual
  transaction, which is a real but recoverable annoyance (the user can
  delete a duplicate) in a personal-finance app with no real money
  movement happening inside these specific calls — not a reason to make
  transaction creation depend on Redis being up.

## Consequences

- Under a Redis outage, idempotency-key protection silently stops working
  rather than the API returning errors — a client retrying a POST during
  that window can create a duplicate. This is an accepted, documented
  tradeoff, not an oversight.
- This decision does **not** apply uniformly to every future Redis use.
  If a later phase adds a feature where Redis genuinely backs a
  correctness guarantee (for example, a distributed lock), that feature
  needs its own explicit fail-open-vs-closed decision — this ADR covers
  cache-shaped uses (idempotency, response caching, rate limiting), not
  every possible Redis use case.

## Validation

`apps/core-api/tests/test_idempotency.py` overrides the `get_redis`
dependency with a stub whose `get`/`set` raise `RedisError`, and asserts
the request still succeeds (fails open) rather than erroring.
