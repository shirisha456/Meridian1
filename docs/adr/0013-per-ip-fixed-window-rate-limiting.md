# ADR-0013: Per-IP, fixed-window rate limiting on /login and /register

## Status

Accepted

## Context

`docs/security.md` documented "no rate limiting on `/login` or `/register`"
as a known gap since Phase 2 — both endpoints are public and unauthenticated
(there is no `user_id` yet to scope by), which makes them the natural target
for credential stuffing (login) and mass fake-account creation (register).
This ADR closes that gap. The fail-open-vs-closed question itself is not
re-litigated here — ADR-0002 already covers Redis-backed cache-shaped
features generally and specifically names rate limiting as one of them.

## Decision

`app/core/rate_limit.py`'s `RateLimiter` is a Redis `INCR`+`EXPIRE`
fixed-window counter, keyed `rate_limit:{action}:{client_ip}` — scoped by
**IP address**, not email, since the goal is slowing down an attacker
hitting the endpoint at all, and keying by email would mean an attacker
could still hammer a *different* email per request with no limit, while a
legitimate user sharing an IP (office NAT, campus network) with someone
else's failed attempts would be unfairly throttled either way. IP is the
only identity signal that exists before authentication succeeds.

Two independent limiters, not one shared budget:
- `/register`: 5 requests / 60s per IP
- `/login`: 10 requests / 60s per IP (login is a normal, repeatable action
  for a legitimate multi-user IP in a way that repeated registration isn't)

A fixed window (not sliding window, not token bucket) — one `INCR` and,
only on the first hit, one `EXPIRE`. This is intentionally the simplest
correct implementation: it allows up to 2x the stated limit across a
window boundary in the worst case, which is an acceptable imprecision for
*slowing down* brute-force/credential-stuffing attempts, not a hard
security boundary the way the refresh-token theft detection is.

## Alternatives considered

- **Sliding window / token bucket** — more precise, rejected as
  unnecessary complexity for a throttle whose job is "make automated
  abuse meaningfully slower," not "enforce an exact quota."
- **Per-email instead of per-IP** — rejected: an attacker controls the
  email in the request body, so a per-email limit is trivially bypassed
  by varying the email each attempt, which is exactly the credential-
  stuffing pattern this exists to slow down.
- **A shared limiter across both endpoints** — rejected: register and
  login have different legitimate-traffic shapes (see Decision), so one
  shared budget would either be too strict for login or too loose for
  register.

## Consequences

- A shared-IP legitimate user base (office, campus, CGNAT) can still hit
  the register limit under unusual but real circumstances (e.g. a class
  of students all registering within a minute) — an accepted tradeoff,
  not something this design optimizes away.
- Still no protection against a distributed attack (many IPs, few
  requests each) — this closes the "one IP hammering the endpoint" gap
  specifically, not every abuse pattern; a WAF/CDN-level control would be
  the next layer, out of scope for this app.

## Validation

`apps/core-api/tests/test_rate_limit.py`: requests under the limit
succeed, the request that crosses the limit gets a 429 with
`retry_after_seconds`, login and register are proven independently scoped
(exhausting one doesn't block the other), and a Redis outage is proven to
fail open (login/register keep working, per ADR-0002) via the same
`BrokenRedis` stub `test_idempotency.py` uses.
