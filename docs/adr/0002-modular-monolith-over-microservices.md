# ADR-0002 — Modular monolith over microservices (initially)

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

The product brief lists a "microservice breakdown." Microservices solve *organizational* and *scale* problems: independent deployability for many teams, isolated scaling of hot paths, and fault isolation. PokéQuant, at inception, has one small team, no production traffic, and a strongly-coupled domain (catalog → market data → features → forecast → score/risk/explain). The dominant cost driver is *external data acquisition*, not internal compute.

Microservices would impose network hops, distributed transactions/eventual consistency, per-service CI/CD and observability, and cross-service versioning — a large tax paid before any of their benefits are needed.

## Decision

We will build the application core as a **modular monolith** with strict bounded-context boundaries and hexagonal (ports-and-adapters) layering, deployed as a small number of processes split only along genuine workload seams: **sync API**, **async workers**, **data/ML pipelines**, and **inference**. Cross-module communication goes through typed ports so a module can later be extracted into a service by swapping an in-process adapter for a network adapter, with no domain changes.

## Alternatives considered

- **Microservices from day one.** Maximum isolation/scalability, but massive upfront operational and cognitive cost with no current driver; high risk of distributed-monolith anti-patterns. Rejected now, planned as a *target* decomposition.
- **Unstructured monolith (one big app, no boundaries).** Fastest to start, but rots into a big ball of mud; modules leak into each other's tables; testing and future extraction become impossible. Rejected.
- **Serverless functions per capability.** Cheap at idle, but cold starts, local-dev friction, and stateful ML/pipeline workloads fit poorly. Rejected as the core (may host isolated tasks later).

## Consequences

- Positive: fast iteration, one deploy, simple local dev (`docker-compose up`), transactional consistency, and easy refactoring — while preserving modularity and a clear path to services.
- Negative / cost: discipline required to keep boundaries clean (no cross-module table access); a single deploy unit for the core.
- Follow-ups: enforce boundaries with an import-linter in CI; document the [target microservice decomposition](../01-system-architecture.md#5-target-microservice-decomposition-when-we-outgrow-the-monolith) and the signals that justify each extraction.
