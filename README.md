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

_More added as each phase lands — see the phase table below for what's
actually implemented today versus planned._

## Major features

- Email/password registration and login, Argon2id-hashed, JWT access
  tokens + rotating refresh tokens (Phase 2)
- Manual financial accounts and transactions: paginated listing, merchant
  search, date-range filtering, idempotent creation, cross-user isolation
  (Phase 3)

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
├── services/               Independent Kafka consumers/pollers (added Phase 8+)
├── libs/events/             Shared event contracts (added Phase 7)
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
| 4 | Budgets, goals, and net worth | Planned | |
| 5 | Investments and market data | Planned | |
| 6 | Plaid integration | Planned | |
| 7 | Transactional outbox and events | Planned | |
| 8 | Transaction enrichment | Planned | |
| 9 | Anomaly detection and notifications | Planned | |
| 10 | AI financial insights | Planned | |
| 11 | Frontend | Planned | |
| 12 | Observability | Planned | |
| 13 | Resilience and chaos testing | Planned | |
| 14 | Infrastructure and CI/CD | Planned | |
| 15 | Portfolio documentation | Planned | |

Each phase's design decisions and verification checklist:
[`docs/phase0.md`](docs/phase0.md), [`docs/phase1.md`](docs/phase1.md),
[`docs/phase2.md`](docs/phase2.md), [`docs/phase3.md`](docs/phase3.md)
(others added as their phases land).

## Local development setup

```bash
cd apps/core-api
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d postgres redis   # or `docker compose up -d` for the full infra set
alembic upgrade head                  # creates users, refresh_tokens, categories (seeded), accounts, transactions
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
  `REDIS_URL`. Grows as later phases add Plaid, Kafka, and OpenAI
  configuration.

## Database migrations

Alembic is wired up (`apps/core-api/alembic/`), running against a sync
driver (`psycopg`) independent of the app's async runtime driver — see
[ADR-0001](docs/adr/0001-async-sqlalchemy.md). Migrations so far:
`users`/`refresh_tokens` (Phase 2), `categories` (seeded, idempotently —
see [`docs/phase3.md`](docs/phase3.md)) / `accounts` / `transactions`
(Phase 3).

```bash
cd apps/core-api
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Backend test commands

```bash
cd apps/core-api
pytest -v          # 55 tests: health, errors, config, auth/security, accounts, transactions, idempotency
ruff check .
```

## Frontend commands

Added in Phase 11.

## Docker Compose instructions

`docker-compose.yml` (project name pinned to `meridian-rebuild` — see
[`docs/phase0.md`](docs/phase0.md)) currently starts Postgres
(`localhost:5433`), Redis (`localhost:6380`), Redpanda (`localhost:19092`),
and `core-api` (`localhost:8000`, depends on Postgres and Redis being
healthy, `alembic upgrade head` runs automatically on container start).
The four Kafka/poller services and the observability stack are added in
the phases that build them.

## Observability instructions

Added in Phase 12.

## External integration behavior

Added in Phase 6 (Plaid) and Phase 10 (OpenAI).

## Security highlights

Argon2id password hashing (explicit, OWASP-cited parameters — not library
defaults), JWT access tokens (15 min), rotating refresh tokens with
theft/reuse detection (a replayed already-used-or-revoked token kills its
entire token family), refresh tokens stored only as a SHA-256 hash,
HttpOnly/SameSite=lax cookies scoped to `/api/v1/auth`, and a startup
guard that refuses to boot in production with the placeholder JWT secret.
Documented fully in [`docs/security.md`](docs/security.md) (Phase 15).

## CI/CD summary

`.github/workflows/ci.yml`'s `backend` job installs `apps/core-api`,
runs `alembic upgrade head` against a real Postgres service container,
runs `pytest`, and runs `ruff check .` — on every push to `main` and every
pull request. Frontend checks and the gated chaos smoke test are added in
the phases that introduce them.

## Infrastructure summary

Added in Phase 14.

## Known limitations

No rate limiting on `/login` or `/register` yet. No Plaid, budgets,
goals, investments, net worth, event pipeline, or AI features exist yet
— those are Phases 4-10. Manual accounts/transactions and auth are the
full extent of what's real today.

## Future enhancements

Tracked per-phase; a consolidated list is added in Phase 15.

## Documentation links

- [`docs/adr/`](docs/adr/) — architecture decision records, including
  [ADR-0001: async SQLAlchemy](docs/adr/0001-async-sqlalchemy.md) and
  [ADR-0002: fail-open Redis dependencies](docs/adr/0002-fail-open-redis-dependencies.md)
- [`docs/phase0.md`](docs/phase0.md), [`docs/phase1.md`](docs/phase1.md),
  [`docs/phase2.md`](docs/phase2.md), [`docs/phase3.md`](docs/phase3.md) —
  per-phase design notes and verification checklists

## Demo instructions

Added in Phase 15 ([`docs/demo.md`](docs/demo.md)).
