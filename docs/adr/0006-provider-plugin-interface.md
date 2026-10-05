# ADR-0006 — Typed provider adapter interface

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

Data comes from many heterogeneous, unreliable, rate-limited sources ([02](../02-data-sources.md)): REST APIs (PokemonTCG.io, eBay Browse, FRED), paid APIs (PriceCharting), OAuth clients (Reddit), fragile/unofficial paths (Google Trends via pytrends), and best-effort ones (PSA). Each has a different auth model, rate limit, schema, and failure mode. If ingestion code is coupled to any one source's quirks, adding/replacing a source becomes risky and testing requires live network calls.

## Decision

We will define a small set of **typed provider ports** (Python `Protocol`s / ABCs) that all data adapters implement, and normalize every source into a common domain schema at the adapter boundary. Core ports:

- `MarketDataProvider` — `fetch_observations(instrument, since) -> list[PriceObservation]`
- `SupplyProvider` — `fetch_supply(instrument, at) -> SupplySnapshot` (listing counts, depth)
- `SentimentProvider` — `fetch_sentiment(query, window) -> list[SentimentSignal]`
- `TrendsProvider` — `fetch_interest(term, window) -> InterestSeries`
- `PopulationProvider` — `fetch_population(instrument) -> PopulationReport` (optional/best-effort)
- `MacroProvider` — `fetch_series(code, since) -> MacroSeries`

Each adapter also declares **capabilities and constraints** as metadata: rate-limit budget, freshness/cadence, auth requirement, and reliability tier. A shared **rate-limit orchestrator** (Redis token bucket keyed by provider) enforces budgets across all workers. Adapters are the *only* code allowed to make external calls.

## Alternatives considered

- **Ad-hoc per-source ingestion scripts.** Fast to write, but no shared retry/rate-limit/normalization; every source reinvents the wheel; untestable without the network. Rejected.
- **A generic HTTP "config-driven" ingester (declarative YAML).** Elegant for simple REST sources, but can't express OAuth, pytrends fragility, PriceCharting condition mapping, or eBay's aggregation logic. Rejected as the sole mechanism; a declarative helper may back the simplest REST adapters.
- **A third-party ELT tool (Airbyte/Fivetran/dlt) for everything.** Great for standard connectors, but our sources need domain-specific normalization (condition/currency/instrument resolution) that belongs in our domain. We may use `dlt` inside a few adapters, but the port/normalization contract stays ours. Rejected as the primary abstraction.

## Consequences

- Positive: a new source = one adapter implementing a port + a config entry; adapters are unit-tested against recorded fixtures (no live calls); rate limits are centrally guaranteed; asset-class plugins register their own providers ([ADR-0004](0004-generic-asset-model-and-plugin-registry.md)).
- Negative / cost: an abstraction layer to maintain; normalization logic must be kept faithful to each evolving source.
- Follow-ups: define the normalized schemas and per-source specifics in [02](../02-data-sources.md); record provider runs (rows, errors, latency) for observability.
