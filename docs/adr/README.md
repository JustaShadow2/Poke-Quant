# Architecture Decision Records

An **Architecture Decision Record (ADR)** captures a single significant architectural decision, its context, the alternatives considered, and its consequences. We follow the lightweight format popularized by Michael Nygard. ADRs are immutable once **Accepted**: to change a decision, add a new ADR that supersedes the old one (and mark the old one `Superseded by ADR-XXXX`).

Why we keep ADRs: they make the reasoning behind the system legible to future maintainers (and interviewers), prevent re-litigating settled debates, and force us to write down the alternatives we rejected and *why*.

## Status values

`Proposed` → `Accepted` → (`Deprecated` | `Superseded by ADR-XXXX`)

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-modular-monolith-over-microservices.md) | Modular monolith over microservices (initially) | Accepted |
| [0003](0003-postgres-timescaledb-primary-store.md) | PostgreSQL + TimescaleDB as the primary datastore | Accepted |
| [0004](0004-generic-asset-model-and-plugin-registry.md) | Generic asset model with a plugin registry | Accepted |
| [0005](0005-synthetic-historical-backfill.md) | Calibrated synthetic historical backfill | Accepted |
| [0006](0006-provider-plugin-interface.md) | Typed provider adapter interface | Accepted |
| [0007](0007-explainability-first-class.md) | Explainability as a first-class, mandatory output | Accepted |
| [0008](0008-python-fastapi-backend.md) | Python + FastAPI for the backend/core | Accepted |
| [0009](0009-nextjs-typescript-frontend.md) | Next.js + TypeScript for the web frontend | Accepted |
| [0010](0010-quantile-prediction-intervals.md) | Quantile regression + conformal prediction for intervals | Accepted |

## Template

Copy this into `NNNN-short-title.md` for new decisions.

```markdown
# ADR-NNNN — <Short title in the imperative>

- **Status:** Proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <roles>
- **Supersedes / Superseded by:** <ADR links, if any>

## Context

What is the problem, the forces at play, and the constraints? Keep it factual.

## Decision

The decision we are making, stated plainly ("We will ...").

## Alternatives considered

- **Option A** — pros / cons / why (not) chosen.
- **Option B** — pros / cons / why (not) chosen.

## Consequences

- Positive: ...
- Negative / cost: ...
- Follow-ups / things this forces us to do later: ...
```
