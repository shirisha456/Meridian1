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

_Filled in as each phase lands — see the phase table below for what's
actually implemented today versus planned._

## Major features

_Filled in as each phase lands._

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
├── apps/core-api/         FastAPI backend (added Phase 1+)
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
| 1 | Core API and persistence | Planned | |
| 2 | Authentication and security | Planned | |
| 3 | Accounts and transactions | Planned | |
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

Each phase's design decisions and verification checklist: [`docs/phase0.md`](docs/phase0.md) (others added as their phases land).

## Local development setup

Nothing is runnable as an application yet — Phase 0 only establishes the
skeleton. What works today:

```bash
docker compose config    # validates the infra-only compose file
docker compose up -d     # starts Postgres, Redis, Redpanda
```

Backend/frontend setup instructions are added in Phases 1 and 11
respectively.

## Environment variables

Root `.env.example` covers only compose-level substitution today
(`OPENAI_API_KEY`, `MARKET_DATA_API_KEY`). Per-app `.env.example` files are
added as each app/service is introduced.

## Database migrations

Added in Phase 1 (Alembic).

## Backend test commands

Added in Phase 1.

## Frontend commands

Added in Phase 11.

## Docker Compose instructions

`docker-compose.yml` currently starts Postgres (`localhost:5433`), Redis
(`localhost:6380`), and Redpanda (`localhost:19092`) — infrastructure only.
Application services are added to this file in the phases that build them.

## Observability instructions

Added in Phase 12.

## External integration behavior

Added in Phase 6 (Plaid) and Phase 10 (OpenAI).

## Security highlights

Added in Phase 2, documented fully in [`docs/security.md`](docs/security.md) (Phase 15).

## CI/CD summary

`.github/workflows/ci.yml` currently checks out the repository only. Backend
tests, frontend checks, the Postgres migration check, and the gated chaos
smoke test are added as the phases that introduce them land.

## Infrastructure summary

Added in Phase 14.

## Known limitations

Phase 0 is a skeleton — no application, no database schema, no tests beyond
YAML/compose validation. This section will track real, current limitations
starting once there's a real system to have limitations.

## Future enhancements

Tracked per-phase; a consolidated list is added in Phase 15.

## Documentation links

- [`docs/adr/`](docs/adr/) — architecture decision records (template only so far)
- [`docs/phase0.md`](docs/phase0.md) — this phase's design notes and verification checklist

## Demo instructions

Added in Phase 15 ([`docs/demo.md`](docs/demo.md)).
