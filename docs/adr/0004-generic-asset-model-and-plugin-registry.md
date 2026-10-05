# ADR-0004 — Generic asset model with a plugin registry

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

The strategic thesis is that PokéQuant is an *alternative-assets research platform*, not a Pokémon-specific tool. Pokémon sealed product is the first asset class; MTG, sports cards, watches, comics, etc. should be addable without rewriting the forecasting/scoring/risk/portfolio core. If Pokémon-specific concepts (sets, print runs, ETBs) leak into the core schema and code, extensibility dies.

## Decision

We will model the domain around **asset-class-agnostic** concepts and isolate all class-specific logic behind a **plugin registry**:

- **`AssetClass`** — a registered family (e.g., `pokemon_sealed`).
- **`Instrument`** — a generic tradeable item with common columns (name, category, currency, release_date, ...) plus a typed-but-flexible **attributes** store (JSONB + optional per-class attribute tables) for class-specific fields.
- **Generic time-series, feature store, and forecasting** operate on `(instrument_id, timestamp, value/features)` and never reference class-specific columns.
- A **plugin package** per asset class registers: its **providers** (data adapters), its **attribute schema**, and its **feature definitions**. The core discovers plugins via an entry-point registry.

Adding an asset class = writing a plugin, not editing the core.

## Alternatives considered

- **Pokémon-specific schema now, "generalize later."** Faster short-term, but "later" never comes cleanly; retrofitting a generic model onto a Pokémon-shaped schema is a migration nightmare. Rejected — the abstraction is the whole point.
- **Fully generic key-value everything (EAV).** Maximum flexibility, but unqueryable, untyped, and slow. Rejected in favor of common typed columns + JSONB for the long tail + optional per-class typed tables where query performance matters.
- **One schema per asset class (separate tables).** Strong typing per class, but the core would need class-aware branching everywhere. Rejected; plugins encapsulate class specifics instead.

## Consequences

- Positive: the core (forecasting, scoring, risk, explainability, portfolio, UI) is written once and reused for every asset class; onboarding a new class is a contained, testable unit of work; this is a compelling architecture story.
- Negative / cost: an upfront abstraction tax (registry, ports, attribute modeling) before the second asset class exists; JSONB attributes need discipline (validated by the plugin's Pydantic schema).
- Follow-ups: specify provider ports in [ADR-0006](0006-provider-plugin-interface.md); define the instrument/attribute schema in [03](../03-database-design.md); prove the abstraction by shipping a second asset-class plugin in Phase 5 ([12](../12-roadmap.md)).
