# PokéQuant Design Specification

This directory contains the complete system design for **PokéQuant**, a quantitative alternative-assets research platform. It is written to be read top-to-bottom, but each chapter is self-contained. Diagrams are authored inline as [Mermaid](https://mermaid.js.org/); Architecture Decision Records live in [`adr/`](adr/README.md).

## How to read this spec

If you have 10 minutes, read [`00-overview.md`](00-overview.md) and [`01-system-architecture.md`](01-system-architecture.md). If you are evaluating the data/ML depth, jump to [`02`](02-data-sources.md), [`04`](04-feature-engineering.md), and [`05`](05-machine-learning.md). If you are evaluating product thinking, read [`10`](10-ux-design.md) and [`11`](11-ai-features.md).

## Chapters

| # | Chapter | What it covers |
|---|---------|----------------|
| 00 | [Overview](00-overview.md) | Vision, positioning, target users, product pillars, glossary, non-goals, success metrics |
| 01 | [System Architecture](01-system-architecture.md) | C4 views, modular-monolith → microservice decomposition, data-flow & sequence diagrams, folder structure, dependency graph, technology tradeoffs |
| 02 | [Data Sources](02-data-sources.md) | Per-source access model, rate limits, legal/ToS, schema, reliability, cadence, failure modes, and the synthetic-backfill strategy |
| 03 | [Database Design](03-database-design.md) | ERD, generic asset model, TimescaleDB hypertables, per-table columns/types/keys/indexes/normalization |
| 04 | [Feature Engineering](04-feature-engineering.md) | Full feature catalog with formula, rationale, leakage risk, and expected predictive power |
| 05 | [Machine Learning](05-machine-learning.md) | Model zoo comparison, walk-forward validation, metrics, prediction intervals, calibration, HPO, model registry |
| 06 | [Investment Score](06-investment-score.md) | The 0–100 composite score: sub-scores, normalization, weighting, calibration |
| 07 | [Risk Engine](07-risk-engine.md) | Risk taxonomy, probability × severity scoring, natural-language risk narratives |
| 08 | [Explainable AI](08-explainable-ai.md) | SHAP pipeline, global/local attributions, guarded natural-language generation |
| 09 | [Similarity Search](09-similarity-search.md) | Embeddings, `pgvector` ANN, clustering, lifecycle-aligned historical analogues |
| 10 | [UX Design](10-ux-design.md) | Pages, wireframes, component breakdown, terminal-style design system |
| 11 | [AI Features](11-ai-features.md) | Research assistant, Monte Carlo, scenario/what-if, alerts, daily market summary |
| 12 | [Roadmap](12-roadmap.md) | Phased delivery plan with complexity, time, risks, and deliverables |
| 13 | [Engineering Standards](13-engineering-standards.md) | Clean architecture, SOLID, DI, testing, logging, config, Docker, CI/CD |

## Conventions used in this spec

- **Instrument** = a specific tradeable product (e.g., "Prismatic Evolutions Elite Trainer Box"). **Asset class** = a family of instruments (e.g., `pokemon_sealed`).
- **Forecast horizon** defaults to 30/90/365 days unless stated otherwise.
- Code identifiers, table names, and file paths are in `monospace`.
- Every non-trivial decision includes a rationale and the alternatives considered; the largest ones are promoted to [ADRs](adr/README.md).
- RFC 2119 keywords (MUST / SHOULD / MAY) are used where a requirement is normative.

## Related documents

- [Architecture Decision Records](adr/README.md) — the "why" behind the biggest choices.
- [Diagram sources](diagrams/README.md) — Mermaid source copies for reuse in slides/whiteboards.
