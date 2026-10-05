# 06 — Investment Score

The **PokéQuant Investment Score (PQ Score)** is a single, transparent **0–100** rating that answers "how attractive is this instrument as an investment right now?" It is not a black box: it is a **weighted, decomposable composite** of interpretable sub-scores, calibrated so that higher scores correspond to better realized outcomes. Every component is stored ([03 §9](03-database-design.md#9-derived-signals)) so the score is fully auditable and explainable ([08](08-explainable-ai.md)).

## 1. Design goals

- **Transparent & decomposable** — the user can see exactly why the score is what it is.
- **Comparable** — scores are cross-sectionally normalized so a 75 means the same thing across categories.
- **Calibrated** — the score's *ordering* is validated against realized forward returns (higher bucket → higher realized return, on average).
- **Robust** — degrades gracefully when a feature group is missing; never over-trusts thin data.
- **Separable from risk** — expected reward and risk are scored separately, then combined; a high-return, high-risk item should not masquerade as "safe."

## 2. Components (sub-scores)

Each raw signal is converted to a **cross-sectional percentile within the asset class/category** (per date) and expressed on 0–100 (`c_k`). Percentile normalization is regime-robust ("relative to peers now") and makes components comparable.

| Component | Symbol | Raw signal (as-of t) | Direction | Source |
|-----------|--------|----------------------|-----------|--------|
| Expected return | `c_er` | model median forecast return `target_h` | higher better | [05](05-machine-learning.md) |
| Risk-adjusted return | `c_ra` | `forecast_return / predicted_volatility` (Sharpe-like) | higher better | [05](05-machine-learning.md) |
| Valuation gap | `c_val` | `(fair_value − price)/price`, blended with `ev_to_price` | undervalued better | [04 §4.5](04-feature-engineering.md#45-chase-card--expected-value-features) |
| Momentum | `c_mom` | `momentum_90` (rank) | higher better | [04 §4.1](04-feature-engineering.md#41-price--technical-features) |
| Supply trend | `c_sup` | `−supply_growth_90d` (declining supply is bullish) | higher better | [04 §4.2](04-feature-engineering.md#42-supply-liquidity--demand-pressure-features) |
| Demand trend | `c_dem` | attention/sentiment momentum composite | higher better | [04 §4.4](04-feature-engineering.md#44-attention--sentiment-features) |
| Liquidity | `c_liq` | `liquidity_score` (turnover, depth, spread) | higher better | [04 §4.2](04-feature-engineering.md#42-supply-liquidity--demand-pressure-features) |
| Model confidence | `c_conf` | inverse interval width + calibration history | higher better | [05 §5](05-machine-learning.md#5-prediction-intervals--calibration) |

And two **penalties** (they subtract, so the score honestly reflects downside):

| Penalty | Symbol | Signal | Source |
|---------|--------|--------|--------|
| Reprint risk | `p_rep` | `reprint_probability × severity` | [07](07-risk-engine.md) |
| Overall risk drag | `p_risk` | scaled `overall_risk` (bubble/oversupply/liquidity/macro) | [07](07-risk-engine.md) |

## 3. Aggregation

```
raw = Σ_k w_k · c_k          (reward + confidence components)
PQ  = clip( raw − λ_rep·p_rep − λ_risk·p_risk , 0, 100 )
```

Then a **monotonic calibration** map `g(·)` (isotonic regression fit on realized outcomes; see §5) is applied so the final published score's buckets are monotonic in realized forward return:

```
PQ_score = g(PQ)
```

Design choices:

- **Additive, weighted form** (not a multiplicative or opaque ML score) is deliberate: additivity makes each component's **contribution = `w_k · c_k`** directly reportable, which is what powers the "why" breakdown in the UI and mirrors the SHAP-additive philosophy of [08](08-explainable-ai.md).
- Penalties are **subtractive** rather than folded into components so that risk is visibly separable and never hidden inside a "return" number.

## 4. Default weights and profiles

Weights sum to 1 across reward+confidence components; penalty coefficients `λ` are set so a maximal risk can meaningfully depress the score. Defaults (the "Balanced" profile) reflect the domain prior that **supply/valuation/expected-return dominate**, tempered by confidence:

| Component | Balanced | Value | Momentum | Conservative |
|-----------|:-------:|:-----:|:--------:|:------------:|
| Expected return `w_er` | 0.22 | 0.18 | 0.24 | 0.16 |
| Risk-adjusted `w_ra` | 0.16 | 0.16 | 0.12 | 0.24 |
| Valuation `w_val` | 0.16 | 0.26 | 0.08 | 0.16 |
| Momentum `w_mom` | 0.12 | 0.06 | 0.24 | 0.06 |
| Supply trend `w_sup` | 0.14 | 0.14 | 0.12 | 0.14 |
| Demand trend `w_dem` | 0.08 | 0.06 | 0.14 | 0.06 |
| Liquidity `w_liq` | 0.06 | 0.06 | 0.04 | 0.10 |
| Confidence `w_conf` | 0.06 | 0.08 | 0.02 | 0.08 |
| Reprint `λ_rep` | 0.15 | 0.15 | 0.10 | 0.25 |
| Risk drag `λ_risk` | 0.15 | 0.12 | 0.10 | 0.25 |

- **Profiles** let a user weight to taste (e.g., a value investor upweights valuation and downweights momentum). The Balanced profile is the default and the one calibrated/backtested by default.
- **Weight governance:** default weights are set by domain reasoning, then **sanity-checked by fitting a constrained, monotonic model** (e.g., non-negative logistic/GBM on "did it outperform peers over horizon h") to confirm the sign/rough-magnitude of each weight. We keep the hand-set interpretable weights unless the data strongly and stably disagrees — we explicitly avoid a fully-learned opaque weighting, because interpretability is the point.

## 5. Calibration & validation

- **Reliability:** bucket instruments by score decile and measure **realized** forward return per bucket over held-out time (walk-forward). A good score is **monotonic**: decile 10 > decile 9 > … The isotonic map `g` enforces/《repairs》 monotonicity of the published score.
- **Backtest:** does a top-decile PQ basket outperform a naive/random basket net of a modeled spread? This is the economic test ([05 §3](05-machine-learning.md#3-validation-not-fooling-ourselves)).
- **Stability:** the score should not thrash day-to-day without cause; we smooth inputs and monitor score volatility.
- **Recalibration:** `g` and the sanity weights are refit periodically as real history grows.

## 6. Bands and presentation

| Score | Band | Meaning |
|-------|------|---------|
| 90–100 | A+ | Strong opportunity, high conviction |
| 80–89 | A | Attractive |
| 70–79 | B | Favorable |
| 55–69 | C | Neutral / mixed |
| 40–54 | D | Unattractive |
| 0–39 | F | Avoid / overvalued or high risk |

The UI shows the band, the numeric score, a **component contribution bar** (`w_k·c_k` and the penalties), and a one-line narrative ([08](08-explainable-ai.md), [10](10-ux-design.md)).

## 7. Worked example (illustrative)

"Prismatic Evolutions ETB," Balanced profile, 90-day horizon:

| Component | `c_k` | `w_k` | contribution |
|-----------|:----:|:----:|:-----------:|
| Expected return | 78 | 0.22 | 17.2 |
| Risk-adjusted | 71 | 0.16 | 11.4 |
| Valuation | 64 | 0.16 | 10.2 |
| Momentum | 82 | 0.12 | 9.8 |
| Supply trend | 74 | 0.14 | 10.4 |
| Demand trend | 80 | 0.08 | 6.4 |
| Liquidity | 60 | 0.06 | 3.6 |
| Confidence | 68 | 0.06 | 4.1 |
| **raw** | | | **73.1** |
| Reprint penalty | `p_rep = 40` | `λ=0.15` | −6.0 |
| Risk drag | `p_risk = 30` | `λ=0.15` | −4.5 |
| **PQ (pre-calibration)** | | | **62.6** |
| **PQ_score = g(62.6)** | | | **~65 (band C, "favorable-neutral")** |

The stored breakdown lets the UI say: *"Score 65 (C). Positives: strong momentum and expected return, declining supply. Drags: moderate reprint risk and elevated overall risk. Confidence: moderate."*

## 8. Guardrails

- **Minimum data coverage:** if too few components are available (e.g., a brand-new instrument with no supply/attention data), the score is withheld or shown as "insufficient data," never faked.
- **Synthetic exclusion:** scores on synthetic data are flagged and excluded from any "advice" surface ([ADR-0005](adr/0005-synthetic-historical-backfill.md)).
- **Confidence gating:** low model confidence caps the maximum achievable score (you cannot be an "A+" if the model isn't sure).
- **Not advice:** the score is a research signal with a persistent disclaimer ([00 §7](00-overview.md#7-scope-and-non-goals)).

Continue to [07 — Risk Engine](07-risk-engine.md).
