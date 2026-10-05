# ADR-0010 — Quantile regression + conformal prediction for intervals

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Quant Research, Engineering
- **Supersedes / Superseded by:** —

## Context

PokéQuant must ship **calibrated uncertainty**, not bare point estimates — the product promises "expected value in one year" and "probability of +25%," both of which require a trustworthy predictive distribution. Collectible returns are heavy-tailed and regime-dependent, so naive Gaussian error bars (± k·σ) would be miscalibrated, especially in the tails users care about most.

## Decision

We will produce intervals in two stages:

1. **Quantile regression** for the raw predictive distribution: LightGBM trained with **pinball loss** at quantiles {0.05, 0.25, 0.5, 0.75, 0.95} (and TFT's native quantile heads where used).
2. **Conformalized Quantile Regression (CQR)** on a held-out calibration set to adjust interval widths so empirical coverage matches the nominal level with distribution-free, finite-sample guarantees.

We continuously monitor **PICP** (coverage) and **MPIW** (width); coverage drift triggers recalibration/retraining. A **model-confidence** signal is derived from normalized inverse interval width + historical calibration and consumed by the Investment Score and risk narrative.

## Alternatives considered

- **Gaussian ± k·σ from residual variance.** Trivial, but assumes symmetry/normality that collectible returns violate; miscalibrated tails. Rejected.
- **Bayesian models / MC-dropout / deep ensembles.** Principled uncertainty, but heavier to train/serve and still not coverage-guaranteed without calibration. Deferred; conformal wrapping gives guarantees more cheaply.
- **NGBoost (native probabilistic GBM).** Attractive; a viable ensemble member, but ties us to a specific parametric form. Kept as an option, not the primary path.
- **Quantile regression alone (no conformal).** Simple, but quantile models are frequently under/over-covered out-of-sample; we'd be shipping wrong confidence. Rejected in favor of quantile + conformal.

## Consequences

- Positive: distribution-free coverage guarantees; asymmetric, heavy-tail-aware intervals; a principled confidence signal feeding score/risk/Monte-Carlo; model-agnostic (wraps GBM or TFT).
- Negative / cost: requires a held-out calibration split (slightly less training data) and ongoing coverage monitoring; adds a calibration step to the training flow.
- Follow-ups: implement CQR in `ml/evaluation/`; log PICP/MPIW per model version; wire calibration decay into the drift-triggered retrain in [05 §9](../05-machine-learning.md#9-model-lifecycle--registry).
