# 13 — Engineering Standards

These are the non-negotiable engineering practices for PokéQuant. They exist so the codebase stays production-grade: modular, typed, tested, observable, reproducible, and safe. "No shortcuts, no placeholder code" is a standard, not a slogan.

## 1. Architecture & design principles

- **Clean / hexagonal architecture** ([01 §1](01-system-architecture.md#1-architectural-style)): domain at the center, dependencies point inward, frameworks/DBs/APIs are outbound adapters behind ports. The `domain` layer imports no framework code.
- **Bounded contexts / modular monolith** ([ADR-0002](adr/0002-modular-monolith-over-microservices.md)): each module owns its data and exposes a public interface; no cross-module table access; dependency direction enforced by an **import-linter** in CI.
- **SOLID, concretely:**
  - **S**RP — a module/class has one reason to change (e.g., `ForecastService` forecasts; it does not fetch data — a repository does).
  - **O**CP — new data sources/models/asset classes are added as new adapters/plugins, not by editing core switch-statements ([ADR-0004](adr/0004-generic-asset-model-and-plugin-registry.md), [ADR-0006](adr/0006-provider-plugin-interface.md)).
  - **L**SP — every `MarketDataProvider` is substitutable; tests run against the port, not a concrete client.
  - **I**SP — small, focused ports (`MarketDataProvider`, `SentimentProvider`, …) rather than one god-interface.
  - **D**IP — services depend on port abstractions; concrete adapters are injected.
- **Repository pattern** — persistence is hidden behind repository interfaces returning domain entities; SQLAlchemy lives only in adapters.
- **Dependency injection** — constructor injection wired via FastAPI `Depends` (and a lightweight container where useful); this is what makes units testable with fakes and modules extractable to services.

## 2. Typing & language standards

- **Python:** `mypy --strict`; Pydantic v2 models at every I/O boundary; no untyped public functions; `ruff` (lint) + `black` (format) + `isort`; Python 3.12.
- **TypeScript:** `strict` mode; no `any` (lint-enforced); ESLint + Prettier; the API client's types are **generated from the backend OpenAPI schema**, so the front/back contract is compiler-checked ([ADR-0009](adr/0009-nextjs-typescript-frontend.md)).
- **Contracts first:** shared DTOs are defined once (Pydantic → OpenAPI → generated TS), never hand-duplicated.

## 3. Testing strategy (the pyramid + ML-specific tests)

| Layer | Scope | Tools |
|-------|-------|-------|
| **Unit** | domain logic, transforms, scoring/risk math, feature functions | pytest; **hypothesis** (property-based) for numeric invariants |
| **Integration** | repositories + DB, pipelines, migrations | pytest + **testcontainers** (real Postgres/Timescale), Alembic upgrade/downgrade tests |
| **Contract** | provider adapters vs source schemas | recorded fixtures / VCR-style cassettes — **no live network in tests** |
| **API** | endpoint behavior, auth, error mapping | FastAPI `TestClient` |
| **E2E** | critical user journeys in the browser | **Playwright** |
| **ML tests** | data validation, no-leakage, model behavior, calibration | Great Expectations-style data checks; leakage tests (assert features use only ≤ t data); metamorphic tests (more supply ⇒ lower forecast); calibration assertions |

- **Coverage:** a meaningful line/branch target on domain + application layers (not chasing 100%); coverage is a floor, not the goal.
- **Determinism:** seeds fixed; no test depends on wall-clock/network; flaky tests are quarantined and fixed.
- **CI gate:** all layers (except heavy E2E, which runs on a schedule/PR-label) run on every PR.

## 4. Error handling

- **Typed domain exceptions** mapped centrally to **RFC 9457 `application/problem+json`** responses; no leaking stack traces to clients.
- **Providers:** bounded retries with exponential backoff + jitter, circuit breakers, and idempotent pipeline steps so re-runs are safe ([01 §8](01-system-architecture.md#8-cross-cutting-concerns)).
- **Fail loud internally, degrade gracefully externally:** a down Tier-3 source disables its features (with a badge) rather than failing the request ([02 §3](02-data-sources.md#3-reliability-tiers)).

## 5. Logging, observability & SLOs

- **Structured JSON logging** via `structlog`; one event per line; **correlation/request IDs** propagated API → worker → pipeline.
- **OpenTelemetry** traces + **Prometheus** metrics + **Grafana** dashboards + **Loki** logs + **Tempo/Jaeger**; **Sentry** for exceptions.
- **Domain metrics:** ingest rows/errors per source, budget consumption, snapshot completeness, prediction latency, cache hit rate, model staleness, interval calibration (PICP), drift.
- **SLOs** (from Phase 4): API availability + p95 latency targets, pipeline freshness (snapshots by a daily deadline), and calibration bounds; alerting on breach.

## 6. Configuration & secrets

- **12-factor:** all config via environment, parsed/validated by **Pydantic Settings**; typed settings objects, no scattered `os.getenv`; per-environment overlays.
- **Secrets:** never committed; local `.env` (git-ignored) → **SOPS**-encrypted files or a managed store (AWS Secrets Manager/Doppler) in deployed envs; least-privilege per-provider credentials; rotation supported.
- **Feature flags:** notably `ALLOW_SYNTHETIC_IN_SCORING=false` by default ([ADR-0005](adr/0005-synthetic-historical-backfill.md)).

## 7. Data & ML reproducibility

- **Append-only raw + point-in-time features** guarantee no look-ahead and full historical reconstruction ([01 §6](01-system-architecture.md#6-end-to-end-data-flow)).
- **Versioned datasets** (parquet in object storage), **versioned feature sets**, and **tracked training runs** (MLflow) mean any model is reproducible; every `prediction` references its exact `model_version_id` + `feature_set_id` ([03 §8](03-database-design.md#8-ml-lifecycle)).
- **Seeds fixed** for training; environment pinned; artifacts hashed.

## 8. Containerization & local dev

- **Docker:** multi-stage builds (slim runtime images, non-root user, pinned base images); one image per deployable (api, worker, pipeline, inference, web).
- **`docker-compose`** for local: app + Postgres/Timescale + Redis + MinIO + MLflow + observability — **one-command bring-up** is a hard requirement.
- **Task runner** (`make`/`justfile`): `setup`, `up`, `test`, `lint`, `typecheck`, `migrate`, `seed`, `synth` (generate synthetic data), `fmt`.

## 9. CI/CD

GitHub Actions pipeline, fast and blocking on quality:

```mermaid
flowchart LR
    pr["PR opened"] --> lint["Lint + format check (ruff/black/eslint/prettier)"]
    lint --> types["Type check (mypy --strict / tsc)"]
    types --> unit["Unit + integration tests (testcontainers)"]
    unit --> contract["Adapter contract tests (fixtures)"]
    contract --> build["Build images"]
    build --> scan["Dependency + image scan, SBOM"]
    scan --> e2e["E2E (Playwright) [scheduled/label]"]
    e2e --> deploy["Deploy (staging -> prod on approval)"]
```

- **Pre-commit hooks** mirror CI (format, lint, type, secret-scan) to catch issues before push.
- **Migrations** run automatically to a disposable DB in CI (upgrade + downgrade verified).
- **Supply chain:** pinned deps + lockfiles (`uv.lock`, `pnpm-lock.yaml`), `pip-audit`/`npm audit`, image scanning, SBOM generation.
- **Deploys:** staging on merge; production behind manual approval; blue/green or canary at Track B ([01 §10](01-system-architecture.md#10-deployment-strategy-two-tracks)).

## 10. Version control & collaboration

- **Trunk-based-ish** with short-lived feature branches; small, reviewable PRs.
- **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`) enabling automated changelogs / **semantic versioning**.
- **PR requirements:** green CI, at least one review (or self-review checklist for solo), updated tests, and an **ADR** when an architecturally significant decision changes ([adr/](adr/README.md)).

## 11. Documentation standards

- **Code:** docstrings on public interfaces (purpose, args, returns, raises); comments explain **why**, never restate **what**.
- **API:** auto-generated **OpenAPI**; kept accurate by contract tests + generated client.
- **Design:** this `docs/` set is the living design of record; **ADRs** capture decisions; diagrams are inline Mermaid ([diagrams/](diagrams/README.md)).
- **READMEs:** repo root + each app explain setup and purpose; runbooks for operational tasks (Phase 4).

## 12. Definition of Done

A change is "done" when: it is typed and formatted; unit/integration (and relevant ML) tests pass and cover the new logic; it has no new lint/type/security findings; observability (logs/metrics) is added for new behavior; docs/ADRs updated if needed; config/secrets handled correctly; it degrades gracefully on dependency failure; and CI is green. For ML changes, add: leakage checked, walk-forward evaluated, calibration not regressed, run tracked in MLflow, and the model version wired into `predictions` for reproducibility.

---

This concludes the design specification. Return to the [documentation index](README.md), or review the decisions behind it in the [ADRs](adr/README.md). Implementation begins at [Phase 1](12-roadmap.md#phase-1--mvp-foundation) upon approval.
