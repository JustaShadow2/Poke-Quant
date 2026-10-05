# ADR-0005 — Calibrated synthetic historical backfill

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering, Quant Research
- **Supersedes / Superseded by:** —

## Context

There is no free, legal, historical time series for sealed-product prices ([02 §1](../02-data-sources.md#1-the-core-problem-historical-sealed-price-data-is-scarce-and-gated)): eBay sold history (Marketplace Insights) is restricted, TCGplayer's API is closed, PriceCharting's API is current-only, and PokemonTCG.io covers singles. We only accumulate real sealed history *forward* from launch. But we need history *now* to build and validate the full pipeline (features → models → intervals → scores → explanations → UI) and to bootstrap models before enough real data exists.

## Decision

We will implement a **calibrated synthetic historical generator** that produces realistic per-instrument price/supply/attention series, used strictly for **development, automated testing, and model bootstrapping** — never as an undisclosed input to user-facing advice.

Calibration and realism:

- **Anchors:** real MSRP at release and the current observed price pin the endpoints of each trajectory.
- **Lifecycle model:** sealed products follow a characteristic curve (near-release softness, appreciation after print/sell-through cutoff as supply declines), with **holiday/Q4 seasonality** and occasional **reprint shocks** and **regime switches** (bull/bear/collapse).
- **Stochastic process:** GBM-style returns with fat tails; **cross-sectional correlation** so products in the same set co-move; correlated **supply** (declining active listings) and **attention** (search/social) series so engineered features are realistic, not independent noise.
- **Quarantine:** every generated row is tagged `data_source = 'synthetic'`. It is excluded from production scoring/advice paths and from any "real performance" claim; it may power a clearly-labeled demo mode.

## Alternatives considered

- **Wait for real data before building models.** Honest, but blocks all ML/product development for months and prevents testing the pipeline. Rejected.
- **Scrape gated sources to fabricate history.** Would violate ToS (eBay/TCGplayer/PSA) and create legal risk — directly against our data principles. Rejected.
- **Use an unrelated public financial dataset as a stand-in.** Exercises code but has the wrong statistical structure (no reprint shocks, no lifecycle, wrong seasonality), so validation would be misleading. Rejected.
- **Naive random walk.** Trivial to build but unrealistic (no lifecycle/seasonality/correlation), so models would learn nothing transferable. Rejected in favor of a structured, calibrated generator.

## Consequences

- Positive: the entire system can be built, integration-tested, and demoed end-to-end, legally and offline; models have a sensible bootstrap; the generator doubles as a scenario/stress tool.
- Negative / cost: synthetic ≠ real — metrics on synthetic data are *illustrative only*; there is a risk of over-fitting to the generator's assumptions. Mitigations: keep the generator simple and documented, gate all "advice" on real data, and re-validate on real history as it accrues.
- Follow-ups: implement under `data/synthetic/`; document assumptions and parameters; add a config flag (`ALLOW_SYNTHETIC_IN_SCORING=false` by default); track real-vs-synthetic data coverage per instrument and surface it in the UI/admin.
