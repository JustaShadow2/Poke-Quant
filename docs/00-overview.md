# 00 — Overview

## 1. Vision

**PokéQuant is a quantitative research platform for alternative assets.** It brings the rigor of equity/quant research — clean market data, engineered features, calibrated forecasts, risk models, and explainability — to markets that have historically had none: collectibles.

The first supported **asset class** is Pokémon *sealed* product (Elite Trainer Boxes, Booster Boxes, Booster Bundles, Collection Boxes, Premium Collections, UPCs, Pokémon Center exclusives). The platform is deliberately architected so that Pokémon is a *plugin*, not the product. The forecasting engine, scoring, risk models, portfolio logic, and UI are asset-class-agnostic.

One sentence: **"Bloomberg Terminal + Zillow Zestimate + Morningstar for collectible investments, starting with Pokémon."**

## 2. The problem

Collectible markets are large but structurally inefficient:

- **Fragmented price discovery.** The "price" of a product differs across eBay, TCGplayer, PriceCharting, local game stores, and auction houses. There is no consolidated tape.
- **No standard fair value.** Unlike equities, there is no widely accepted valuation model. Buyers rely on vibes, hype cycles, and anecdotes.
- **Illiquidity and asymmetry.** Spreads are wide, sellers know more than buyers, and "is this a good buy?" is genuinely hard to answer.
- **Signal is scattered across alternative data.** Demand shows up first in search interest, YouTube openings, and community sentiment — not in price.
- **Supply is opaque.** Print runs are undisclosed; reprints can crater a product overnight.

These are exactly the conditions under which a quantitative, data-driven approach adds value.

## 3. What PokéQuant does

For any tracked instrument, PokéQuant answers the questions a serious buyer actually asks:

- *Should I buy this product?* → **Investment Score (0–100)** with a full breakdown ([06](06-investment-score.md)).
- *Is it currently undervalued?* → **Fair-value estimate** vs. current market price.
- *What is its expected value in one year?* → **Forecast with prediction intervals** ([05](05-machine-learning.md)).
- *What is the probability it rises 25%?* → **Monte Carlo** probability of target return ([11](11-ai-features.md)).
- *What similar products behaved like this?* → **Historical analogues** via lifecycle-aligned similarity ([09](09-similarity-search.md)).
- *What are the risks?* → **Risk engine** with probability × severity and narratives ([07](07-risk-engine.md)).
- *Why do you think that?* → **SHAP-backed natural-language explanation** on every prediction ([08](08-explainable-ai.md)).

The goal is not "a price predictor." The goal is an **intelligent, explainable investment research assistant.**

## 4. Product pillars

1. **Historical price tracking** — a consolidated, deduplicated, currency-normalized time series per instrument.
2. **AI price forecasting** — multi-horizon (30/90/365d) point + interval forecasts from an ensemble.
3. **Investment Score** — a transparent, decomposable 0–100 rating.
4. **Risk engine** — reprint, bubble, oversupply, liquidity, and macro risks with severities.
5. **Explainable AI** — SHAP + guarded NL summaries; never a black box.
6. **Similar-product discovery** — "this looks like Hidden Fates did in 2020."
7. **Portfolio management** — holdings, cost basis, P&L, exposure, and portfolio-level risk.
8. **Market analytics** — sector/set-level indices, movers, breadth, liquidity heatmaps.
9. **Supply & demand analysis** — listing depth, sell-through, search/attention trends.
10. **Automated data collection** — scheduled, rate-limit-aware ingestion building a proprietary dataset.

## 5. Target users

| Persona | Need | Key surfaces |
|---------|------|--------------|
| The serious collector-investor | "Is this a smart buy at this price?" | Product page, Investment Score, forecast, risk |
| The flipper / trader | "What's moving and mispriced right now?" | Market overview, undervalued scanner, alerts |
| The portfolio holder | "How is my collection doing and where's my risk?" | Portfolio, exposure, portfolio review |
| The analyst / skeptic | "Show me the data and why you believe it" | Charts, feature attributions, analogues, methodology |
| The operator (internal/admin) | "Is the pipeline healthy? Are models drifting?" | Admin dashboard, data/model observability |

## 6. Design philosophy

- **Build a startup, not a demo.** Every component is production-shaped: typed, tested, observable, and deployable.
- **Extensibility is the thesis.** The multi-asset abstraction ([ADR-0004](adr/0004-generic-asset-model-and-plugin-registry.md)) is what turns "Pokémon price predictor" into "alternative-assets research platform."
- **Legality and reliability drive the data design.** We only use permitted/free access paths and are explicit about every source's constraints ([02](02-data-sources.md)).
- **Uncertainty is a feature.** We ship calibrated intervals and confidence, not false-precision point estimates.
- **Explainability is non-negotiable.** If we cannot explain a prediction, we do not surface it as advice.
- **Judgment over resume-driven design.** We start as a modular monolith and extract services only when justified ([ADR-0002](adr/0002-modular-monolith-over-microservices.md)).

## 7. Scope and non-goals

**In scope (platform):** ingestion, storage, features, forecasting, scoring, risk, explainability, similarity, portfolio, alerts, analytics, an AI assistant, and the web UI.

**Explicit non-goals (at least through Phase 4):**

- **Not a marketplace / brokerage.** PokéQuant does not execute trades, hold inventory, or take custody.
- **Not financial advice.** Outputs are research signals with disclaimers; no fiduciary role.
- **Not a grading/authentication service.** We consume grading population data where permitted; we do not grade.
- **No scraping of sources that prohibit it.** Where a source's ToS forbids automated collection (e.g., PSA population reports), we treat it as optional/best-effort and clearly caveated ([02](02-data-sources.md)).
- **No real-money guarantees.** Backtests and forecasts are illustrative, not promises.

## 8. Success metrics

**Model quality:** directional accuracy > naive baseline; MAPE within a documented target band per horizon; interval calibration (empirical coverage ≈ nominal, e.g., 90% PI covers ~90%). See [05](05-machine-learning.md).

**Product quality:** every forecast has a stored explanation; p95 product-page latency budget met; scanner surfaces opportunities that outperform a random/naive basket in backtest.

**Engineering quality:** typed (mypy strict), tested (coverage target), reproducible training runs (tracked in the model registry), one-command local bring-up, green CI.

## 9. Glossary

| Term | Definition |
|------|------------|
| **Asset class** | A family of tradeable items sharing data providers and attributes, e.g. `pokemon_sealed`. |
| **Instrument** | A single tracked product, e.g. "Prismatic Evolutions ETB." The unit of forecasting. |
| **Observation** | A single price data point for an instrument from one source at one time. |
| **Snapshot** | A daily consolidated price/supply record per instrument (the modeling grain). |
| **Feature** | A derived, point-in-time signal used by models (e.g., 30-day momentum). |
| **Feature vector** | The full set of features for one instrument at one timestamp. |
| **Forecast horizon** | Days ahead a prediction targets (default 30/90/365). |
| **Prediction interval (PI)** | A calibrated range (e.g., 90%) around a forecast. |
| **Investment Score** | The proprietary 0–100 composite rating ([06](06-investment-score.md)). |
| **Provider / adapter** | A pluggable client for one external data source implementing a typed interface. |
| **Plugin** | An asset-class package registering providers, attributes, and features. |
| **Analogue** | A historical instrument whose lifecycle trajectory resembles the target's. |
| **Sell-through / sold-listed ratio** | A proxy for demand vs. supply pressure. |
| **Reprint risk** | The probability the manufacturer reissues a product, pressuring price. |

## 10. Reading path

Continue to [01 — System Architecture](01-system-architecture.md). The end-to-end delivery plan is in [12 — Roadmap](12-roadmap.md); the decisions behind the big choices are in the [ADRs](adr/README.md).
