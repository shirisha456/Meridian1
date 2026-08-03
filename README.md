# Meridian

A cloud-native personal finance and investment platform: accounts and
transactions, Plaid bank sync, budgets and savings goals, investment
tracking, an event-driven pipeline (Kafka/Redpanda) that categorizes
transactions and detects anomalies in real time, AI-generated monthly
insights, and full observability across the async pipeline.

This repository is being rebuilt from an earlier version in incremental,
reviewed phases — see [Development phases](#development-phases) below.
Every phase's design decisions live in its own doc under `docs/`, and
every architectural decision worth remembering has an ADR under
[`docs/adr/`](docs/adr/).

## Problem this solves

Personal finance data is scattered across banks, brokerages, and manual
tracking, and turning it into a single accurate picture — accounts,
spending by category, budget adherence, net worth, investment performance —
usually means either a spreadsheet or trusting a third party with
read access to every account. Meridian centralizes that view behind
authentication you control, syncs transactions automatically where
possible (Plaid), and processes them asynchronously so categorization
and anomaly detection don't block the request that created them.

## Key engineering highlights

- Rotating refresh tokens with **theft/reuse detection**: a refresh token
  presented twice (already used or already revoked) kills its entire
  token family, not just itself — see
  [ADR discussion in docs/phase2.md](docs/phase2.md)
- Async SQLAlchemy 2.0 end-to-end, not sync calls threadpooled under
  async routes — see [ADR-0001](docs/adr/0001-async-sqlalchemy.md)
- One consistent error envelope for every failure path (deliberate,
  validation, routing, and unhandled exceptions alike) — see
  [`docs/phase1.md`](docs/phase1.md)
- A per-account, DB-level unique constraint backing transaction dedupe
  (the reference implementation's dedupe check was app-level-only and
  had a real race condition) — see [`docs/phase3.md`](docs/phase3.md)
- Idempotency-key protected transaction creation, Redis-backed, fails
  open on a Redis outage rather than blocking writes — see
  [ADR-0002](docs/adr/0002-fail-open-redis-dependencies.md)
- Cache invalidation scoped to what a write actually affects, not
  blanket invalidation of every plausibly-related key — see
  [`docs/phase4.md`](docs/phase4.md)
- Optional external integrations (market data, Plaid) fail as a typed
  503 via the shared error model, never a mock/synthetic value standing
  in for real data — see [`docs/phase5.md`](docs/phase5.md)
- Plaid access tokens encrypted at rest (Fernet, a documented KMS
  stand-in — [ADR-0003](docs/adr/0003-local-envelope-encryption-stand-in.md));
  a real REST client instead of the official SDK specifically because
  that SDK is synchronous and would violate ADR-0001; a `has_more` sync
  loop and a `status=error` transition the reference implementation
  didn't have — see [`docs/phase6.md`](docs/phase6.md)
- Proved migration reversibility for real (`upgrade` → `downgrade base`
  → `upgrade`, not just written and assumed to work) — caught and fixed
  a Postgres-native-enum cleanup bug this way, in both a new and an
  already-committed migration — see [`docs/phase6.md`](docs/phase6.md)
- Transactional outbox with the publish-then-mark ordering bug fixed by
  construction (a row is only marked published *after* Kafka confirms
  delivery), and a Kafka client choice (`aiokafka`, not the sync
  `confluent-kafka` SDK) that keeps the whole app async, not just the
  HTTP layer — see [ADR-0005](docs/adr/0005-transactional-outbox.md),
  [ADR-0006](docs/adr/0006-async-kafka-client.md); verified against a
  real Redpanda broker, not just a fake producer — see
  [`docs/phase7.md`](docs/phase7.md)
- The first independently deployable consumer service
  (`enrichment-service`), with its own minimal-column-subset database
  contract against a schema it doesn't own — see
  [ADR-0007](docs/adr/0007-service-extraction-boundaries.md); verified
  end-to-end running the real consumer process against real Postgres,
  Redis, and Redpanda, not just a fake producer — see
  [`docs/phase8.md`](docs/phase8.md)

_More added as each phase lands — see the phase table below for what's
actually implemented today versus planned._

## Major features

- Email/password registration and login, Argon2id-hashed, JWT access
  tokens + rotating refresh tokens (Phase 2)
- Manual financial accounts and transactions: paginated listing, merchant
  search, date-range filtering, idempotent creation, cross-user isolation
  (Phase 3)
- Per-category monthly budgets with a real budget-vs-actual computation
  (net of refunds, Redis-cached), savings goals, and net-worth snapshots
  with type-based asset/liability classification (Phase 4)
- Investment holdings and a watchlist (get-or-create by ticker symbol),
  with an on-demand price refresh against an optional market-data
  provider (Phase 5)
- Plaid bank linking: link-token creation, public-token exchange,
  encrypted access-token storage, cursor-based transaction sync with
  full `has_more` pagination (Phase 6)
- Transactional outbox + a real Kafka event pipeline: every
  uncategorized transaction publishes a `transactions.ingested` event,
  verified landing on a real Redpanda topic (Phase 7)
- Automatic transaction categorization (rules engine + optional OpenAI
  fallback) and recurring-merchant detection, running as a standalone
  Kafka consumer service (Phase 8)

_More added as each phase lands._

## Architecture

See [`docs/architecture.md`](docs/architecture.md) (added starting Phase 1,
completed in Phase 15) for system diagrams, and the per-phase docs linked
below for how each piece was built.

## Technology stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2 (async), Alembic, PostgreSQL, Redis |
| Event pipeline | Redpanda (Kafka API), shared Pydantic event contracts, transactional outbox, independently deployable consumers |
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand |
| Security | Argon2id, JWT access tokens, rotating refresh tokens, HTTP-only cookies |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Promtail, Tempo |
| Infrastructure | Docker, Docker Compose, GitHub Actions, Terraform, Helm |

## Repository structure

```
meridian/
├── .github/workflows/     CI
├── apps/core-api/         FastAPI backend — config, async DB, errors, health (Phase 1); domain modules added Phase 2+
├── services/
│   └── enrichment-service/ Categorizes transactions.ingested → transactions.enriched (Phase 8)
├── libs/events/             Shared event contracts — a real installable package (Phase 7)
├── web/                    Next.js dashboard (added Phase 11)
├── docs/                   Architecture docs, case study, ADRs, per-phase notes
├── observability/          Prometheus/Grafana/Loki/Promtail/Tempo config (added Phase 12)
├── infra/                  Terraform + Helm (added Phase 14)
├── chaos/                  Chaos/recovery tests (added Phase 13)
├── deploy/                 Production compose, nginx, backup/restore scripts (added Phase 14)
├── docker-compose.yml      Local stack (infra-only until later phases add services)
└── README.md
```

## Development phases

| Phase | Scope | Status | Commit |
|---|---|---|---|
| 0 | Repository foundation | Complete | `chore: initialize Meridian monorepo and development tooling` |
| 1 | Core API and persistence | Complete | `feat: establish core API and PostgreSQL persistence` |
| 2 | Authentication and security | Complete | `feat: add secure authentication and rotating sessions` |
| 3 | Accounts and transactions | Complete | `feat: add accounts and idempotent transaction management` |
| 4 | Budgets, goals, and net worth | Complete | `feat: add budgeting goals and net worth tracking` |
| 5 | Investments and market data | Complete | `feat: add investment portfolio and market data tracking` |
| 6 | Plaid integration | Complete | `feat: integrate Plaid account linking and transaction sync` |
| 7 | Transactional outbox and events | Complete | `feat: introduce transactional outbox and Kafka event contracts` |
| 8 | Transaction enrichment | Complete | `feat: add asynchronous transaction enrichment pipeline` |
| 9 | Anomaly detection and notifications | Planned | |
| 10 | AI financial insights | Planned | |
| 11 | Frontend | Planned | |
| 12 | Observability | Planned | |
| 13 | Resilience and chaos testing | Planned | |
| 14 | Infrastructure and CI/CD | Planned | |
| 15 | Portfolio documentation | Planned | |

Each phase's design decisions and verification checklist:
[`docs/phase0.md`](docs/phase0.md), [`docs/phase1.md`](docs/phase1.md),
[`docs/phase2.md`](docs/phase2.md), [`docs/phase3.md`](docs/phase3.md),
[`docs/phase4.md`](docs/phase4.md), [`docs/phase5.md`](docs/phase5.md),
[`docs/phase6.md`](docs/phase6.md), [`docs/phase7.md`](docs/phase7.md),
[`docs/phase8.md`](docs/phase8.md) (others added as their phases land).

## Local development setup

```bash
cd apps/core-api
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -e ../../libs/events   # shared event contracts — see docs/phase7.md
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d postgres redis redpanda redpanda-topics   # or `docker compose up -d` for everything
alembic upgrade head                  # users, refresh_tokens, categories (seeded), accounts,
                                       # transactions, budgets, goals, net_worth_snapshots,
                                       # securities, security_prices, holdings, watchlist_items,
                                       # institutions, outbox_events
uvicorn app.main:app --reload
```

`GET http://localhost:8000/live`, `/ready`, `/health`, and
`POST http://localhost:8000/api/v1/auth/register` should all respond.
Frontend setup instructions are added in Phase 11.

## Environment variables

- Root `.env.example` — compose-level substitution only (`OPENAI_API_KEY`,
  `MARKET_DATA_API_KEY`)
- `apps/core-api/.env.example` — `DATABASE_URL`, `ENVIRONMENT`, `LOG_LEVEL`,
  `CORS_ORIGINS`, `JWT_SECRET` (must be overridden outside development —
  see `Settings.assert_safe_for_environment`), `JWT_ALGORITHM`,
  `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`,
  `REDIS_URL`, `MARKET_DATA_API_KEY`/`MARKET_DATA_BASE_URL` (optional —
  see [`docs/phase5.md`](docs/phase5.md)), `PLAID_CLIENT_ID`/
  `PLAID_SECRET`/`PLAID_ENV` (optional), `ENCRYPTION_KEY` (required only
  once an institution is actually linked — see
  [ADR-0003](docs/adr/0003-local-envelope-encryption-stand-in.md)),
  `KAFKA_BOOTSTRAP_SERVERS` (defaults to `localhost:19092`, matching
  `docker-compose.yml`'s Redpanda port). Grows as later phases add
  OpenAI configuration.

## Database migrations

Alembic is wired up (`apps/core-api/alembic/`), running against a sync
driver (`psycopg`) independent of the app's async runtime driver — see
[ADR-0001](docs/adr/0001-async-sqlalchemy.md). Migrations so far:
`users`/`refresh_tokens` (Phase 2), `categories` (seeded, idempotently —
see [`docs/phase3.md`](docs/phase3.md)) / `accounts` / `transactions`
(Phase 3), `budgets` / `goals` / `net_worth_snapshots` (Phase 4),
`securities` / `security_prices` / `holdings` / `watchlist_items`
(Phase 5), `institutions` / `accounts.institution_id` /
`accounts.plaid_account_id` (Phase 6), `outbox_events` (Phase 7). Full
reversibility (`downgrade` all the way to base, then `upgrade` back to
head) is verified, not just assumed — see
[`docs/phase6.md`](docs/phase6.md) for a real bug this caught.

```bash
cd apps/core-api
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Backend test commands

```bash
cd apps/core-api
pytest -v          # 98 tests: health, errors, config, auth/security, accounts, transactions,
                   # idempotency, budgets, goals, net worth, investments, encryption,
                   # institutions, outbox
ruff check .

cd ../../libs/events
pytest -v          # 6 tests: event contract shapes, versioning, Topics
ruff check .

cd ../../services/enrichment-service
pytest -v          # 24 tests: rules categorization, AI fallback, db access, full consumer flow
ruff check .
```

## Frontend commands

Added in Phase 11.

## Docker Compose instructions

`docker-compose.yml` (project name pinned to `meridian-rebuild` — see
[`docs/phase0.md`](docs/phase0.md)) currently starts Postgres
(`localhost:5433`), Redis (`localhost:6380`), Redpanda (`localhost:19092`),
a one-shot `redpanda-topics` job that creates every topic in
`meridian_events.Topics`, `core-api` (`localhost:8000`, depends on
Postgres/Redis being healthy and `redpanda-topics` completing
successfully; `alembic upgrade head` runs automatically on container
start), and `enrichment-service` (no exposed port; its `/health` lives
inside the container network only). The remaining Kafka/poller consumer
services and the observability stack are added in the phases that build
them.

## Observability instructions

Added in Phase 12.

## External integration behavior

Market data (Twelve Data, optional — [`docs/phase5.md`](docs/phase5.md)):
without `MARKET_DATA_API_KEY`, `POST /investments/prices/refresh` returns
a 503 and holdings/watchlist entries simply keep `latest_price_minor:
null`, "no price yet" — never a mock/synthetic price.

Plaid (optional — [`docs/phase6.md`](docs/phase6.md)): without
`PLAID_CLIENT_ID`/`PLAID_SECRET`, `/institutions/link-token` and
`POST /institutions` return 503; `GET /institutions` returns `[]` rather
than erroring. When configured, sync is user-triggered (manual or at
link time) — there's no webhook receiver yet, a documented gap, not a
silent one.

OpenAI (optional, `enrichment-service` — [`docs/phase8.md`](docs/phase8.md)):
without `OPENAI_API_KEY`, categorization falls back to the rules engine
only — a merchant the rules don't recognize is simply left uncategorized,
never guessed. The Phase 10 insights feature follows the same contract.

## Security highlights

Argon2id password hashing (explicit, OWASP-cited parameters — not library
defaults), JWT access tokens (15 min), rotating refresh tokens with
theft/reuse detection (a replayed already-used-or-revoked token kills its
entire token family), refresh tokens stored only as a SHA-256 hash,
HttpOnly/SameSite=lax cookies scoped to `/api/v1/auth`, a startup guard
that refuses to boot in production with the placeholder JWT secret, and
Plaid access tokens encrypted at rest (Fernet, a documented KMS
stand-in — [ADR-0003](docs/adr/0003-local-envelope-encryption-stand-in.md)).
Documented fully in [`docs/security.md`](docs/security.md) (Phase 15).

## CI/CD summary

`.github/workflows/ci.yml` runs three jobs on every push to `main` and
every pull request: `events-lib` (installs and tests `libs/events` on
its own), `backend` (installs `libs/events` then `apps/core-api`, runs
`alembic upgrade head` against a real Postgres service container, runs
`pytest`, runs `ruff check .`), and `enrichment-service` (installs
`libs/events` then itself, runs its own test suite and lint). None of
the three spin up a real Redpanda service container — the outbox/Kafka
tests all use a fake producer/consumer; the real-broker round-trip is
verified manually each phase touching it (see
[`docs/phase7.md`](docs/phase7.md), [`docs/phase8.md`](docs/phase8.md)),
matching the reference implementation's own CI scope. Frontend checks
and the gated chaos smoke test are added in the phases that introduce
them.

## Infrastructure summary

Added in Phase 14.

## Known limitations

No rate limiting on `/login` or `/register` yet. `transactions.enriched`
has no consumer yet — that's Phase 9 (anomaly detection). No AI insights
feature yet (Phase 10) — `enrichment-service`'s OpenAI fallback is
categorization only. No dead-letter queue for `enrichment-service`'s
Kafka consumption — a permanently malformed message is logged and
skipped, an accepted, documented gap (see
[`docs/phase8.md`](docs/phase8.md)). Market data is synchronous/on-demand,
not the scheduled poller the reference implementation has — see
[`docs/phase5.md`](docs/phase5.md) for why and when that changes. No
Plaid webhook receiver — sync is user-triggered only (see
[`docs/phase6.md`](docs/phase6.md)). The budgets-goals-networth upsert
operations have a documented, accepted race condition under truly
concurrent identical requests (see [`docs/phase4.md`](docs/phase4.md)) —
not a concern for this app's single-user-driven write pattern.

## Future enhancements

Tracked per-phase; a consolidated list is added in Phase 15.

## Documentation links

- [`docs/adr/`](docs/adr/) — architecture decision records:
  [0001](docs/adr/0001-async-sqlalchemy.md) async SQLAlchemy,
  [0002](docs/adr/0002-fail-open-redis-dependencies.md) fail-open Redis,
  [0003](docs/adr/0003-local-envelope-encryption-stand-in.md) envelope
  encryption stand-in, [0004](docs/adr/0004-event-contract-versioning.md)
  event versioning, [0005](docs/adr/0005-transactional-outbox.md)
  transactional outbox, [0006](docs/adr/0006-async-kafka-client.md)
  async Kafka client, [0007](docs/adr/0007-service-extraction-boundaries.md)
  service extraction boundaries
- [`docs/phase0.md`](docs/phase0.md), [`docs/phase1.md`](docs/phase1.md),
  [`docs/phase2.md`](docs/phase2.md), [`docs/phase3.md`](docs/phase3.md),
  [`docs/phase4.md`](docs/phase4.md), [`docs/phase5.md`](docs/phase5.md),
  [`docs/phase6.md`](docs/phase6.md), [`docs/phase7.md`](docs/phase7.md),
  [`docs/phase8.md`](docs/phase8.md) — per-phase design notes and
  verification checklists

## Demo instructions

Added in Phase 15 ([`docs/demo.md`](docs/demo.md)).
