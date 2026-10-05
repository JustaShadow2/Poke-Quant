# ADR-0008 — Python + FastAPI for the backend/core

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

The core must serve a typed HTTP API *and* sit millimeters from the data/ML stack (pandas/Polars, XGBoost/LightGBM, PyTorch, SHAP, MLflow). We want strong typing, async I/O for fan-out to slow external providers, auto-generated API docs/types, and first-class dependency injection for testability.

## Decision

We will implement the backend in **Python 3.12** with **FastAPI** (+ Pydantic v2, SQLAlchemy 2.0, Alembic). FastAPI's `Depends` provides constructor-style DI; Pydantic gives runtime-validated typed boundaries and auto OpenAPI, from which we generate the frontend's TypeScript client.

## Alternatives considered

- **Split stack: Node/TypeScript API + Python ML service.** Excellent API ergonomics, but introduces a permanent cross-language serialization boundary and duplicate domain models for a system whose core value *is* the ML. Rejected now (the assistant/inference may still be separate Python services later).
- **Go API + Python ML.** Great performance/concurrency for the API, but the same two-language tax, and Go's data/ML ecosystem is thin. Rejected.
- **Django + DRF.** Batteries-included and mature, but heavier, sync-first, and its ORM couples the domain to Django. FastAPI is a better fit for async provider fan-out and a clean hexagonal core. Rejected.
- **Flask.** Minimal, but weaker typing/async story and more boilerplate for validation/docs. Rejected.

## Consequences

- Positive: one language across API, workers, pipelines, and models; typed end-to-end (mypy strict + Pydantic + generated TS types); async fan-out to providers; free OpenAPI.
- Negative / cost: Python's raw throughput trails Go/Rust — mitigated by async I/O, caching, and horizontal scaling of the stateless API; CPU-bound work lives in vectorized libs or the ML plane.
- Follow-ups: enforce `mypy --strict`, `ruff`, and `black`; generate the TS client from OpenAPI in CI ([13](../13-engineering-standards.md)).
