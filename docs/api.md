# API Reference

This is a curated map of every endpoint — grouped by domain, with the
auth requirement and a one-line purpose for each. It is **not** the
authoritative schema reference: `core-api` generates real interactive
OpenAPI docs from its actual Pydantic models, which are guaranteed to
match the running code (this document, being hand-maintained, isn't).

- **Interactive docs (Swagger UI)**: `http://localhost:8000/docs`
- **Raw OpenAPI schema**: `http://localhost:8000/openapi.json`
- **Redoc**: `http://localhost:8000/redoc`

All endpoints except `/live`, `/ready`, `/health`, `/metrics`, and
`/api/v1/auth/{register,login,refresh}` require
`Authorization: Bearer <access_token>`. Every error response uses the
same envelope: `{"error": {"type", "message", "details"}}` — see
`app/errors/exceptions.py`.

## Health & metrics

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/live` | — | Liveness — process is up, no dependency checks |
| GET | `/ready` | — | Readiness — checks the database; 503 if unreachable |
| GET | `/health` | — | Aggregate health for humans/dashboards |
| GET | `/metrics` | — | Prometheus scrape target (`prometheus-fastapi-instrumentator`) |

## Auth (`/api/v1/auth`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/register` | — | Create an account; returns access token + sets refresh cookie |
| POST | `/login` | — | Same response shape as register |
| POST | `/refresh` | cookie | Rotates the refresh token; theft/reuse kills the whole token family |
| POST | `/logout` | Bearer | Revokes the refresh token, clears the cookie |
| GET | `/me` | Bearer | Current user |
| POST | `/ws-ticket` | Bearer | Mints a single-use, 30-second WebSocket auth ticket |

## Accounts (`/api/v1/accounts`)

| Method | Path | Purpose |
|---|---|---|
| POST | `` | Create an account |
| GET | `` | List (paginated — `Page[AccountResponse]`, `limit`/`offset`) |
| GET | `/{id}` | Get one |
| PATCH | `/{id}` | Partial update |
| DELETE | `/{id}` | Delete |

## Transactions (`/api/v1/transactions`)

| Method | Path | Purpose |
|---|---|---|
| POST | `` | Create; auto-fires `transactions.ingested` if uncategorized |
| GET | `` | List (paginated; filters: `account_id`, `category_id`, `date_from`, `date_to`, `q` merchant search) |
| GET | `/{id}` | Get one |
| PATCH | `/{id}` | Partial update |
| DELETE | `/{id}` | Delete |

## Categories (`/api/v1/categories`)

| Method | Path | Purpose |
|---|---|---|
| GET | `` | List (seeded, system categories — not paginated) |

## Budgets (`/api/v1/budgets`)

| Method | Path | Purpose |
|---|---|---|
| PUT | `` | Upsert a category's budget for a month |
| GET | `` | List budgets |
| GET | `/actual` | Budget vs. actual spend per category for a month (`?month=`) |

## Goals (`/api/v1/goals`)

| Method | Path | Purpose |
|---|---|---|
| POST | `` | Create a savings goal |
| GET | `` | List (paginated) |
| PATCH | `/{id}` | Partial update — including progress |
| DELETE | `/{id}` | Delete |

## Net worth (`/api/v1/networth`)

| Method | Path | Purpose |
|---|---|---|
| GET | `` | History (`?days=`, default 90) — cached, point-in-time snapshots |
| POST | `/recompute` | Recompute today's snapshot from current accounts/holdings |

## Investments (`/api/v1/investments`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/holdings` | Add a holding (get-or-create the security by symbol) |
| GET | `/holdings` | List (paginated) |
| DELETE | `/holdings/{id}` | Remove |
| POST | `/watchlist` | Add a symbol to the watchlist (idempotent) |
| GET | `/watchlist` | List |
| DELETE | `/watchlist/{id}` | Remove |
| POST | `/prices/refresh` | Refresh latest prices from the market-data provider (503 if unconfigured) |

## Institutions / Plaid (`/api/v1/institutions`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/link-token` | Create a Plaid Link token (503 if unconfigured) |
| POST | `` | Exchange a public token, link the institution |
| GET | `` | List linked institutions |
| POST | `/{id}/sync` | Pull new/updated transactions via Plaid's cursor sync |
| DELETE | `/{id}` | Unlink |

## Alerts (`/api/v1/alerts`)

| Method | Path | Purpose |
|---|---|---|
| GET | `` | List (real-time via WS push; this is the system of record) |
| PATCH | `/{id}/read` | Mark read |

## Insights (`/api/v1/insights`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/latest` | Most recent generated insight (404 if none yet) |
| POST | `/generate` | Generate a summary for a period (defaults to current month); 422 if nothing to summarize |

## Real-time

| Protocol | Path | Purpose |
|---|---|---|
| WebSocket | `/ws/live?ticket=<ticket>` | Live `alert`/`insight` push, ticket from `POST /auth/ws-ticket` |

## Notes on conventions

- **Money** is always `_minor` integer units (cents), never a float —
  avoids floating-point rounding errors in financial arithmetic.
- **Pagination**: `accounts`, `transactions`, `goals`, and
  `investments/holdings` return `Page[T]` — `{items, total, limit,
  offset}` (`limit` default 50, max 100). Every other list endpoint
  returns a bare array (small, bounded collections — categories,
  budgets, alerts, watchlist, institutions).
- **Idempotency**: `POST /transactions` accepts an optional
  `Idempotency-Key` header (Redis-backed, fails open on a Redis
  outage — see [ADR-0002](adr/0002-fail-open-redis-dependencies.md)).
- **Ownership**: every resource is scoped to the authenticated user;
  accessing another user's resource by ID returns 404, not 403 (doesn't
  confirm the resource exists at all to an unauthorized caller).
