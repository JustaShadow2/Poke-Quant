# 07 — Risk Engine

Expected return is only half the picture. The **Risk Engine** estimates the ways an instrument can *lose* value, quantifies each as **probability × severity**, aggregates them into an overall risk score with a band, and produces a plain-language risk narrative. Risk is scored **separately** from return and then fed back into the Investment Score as an explicit drag ([06](06-investment-score.md)) — so downside is never hidden inside an upside number.

## 1. Philosophy

- **Decompose, don't blob.** Overall risk is built from named, individually-explainable factors, each with its own probability and severity — mirroring the decomposability of the Investment Score and SHAP explanations.
- **Probability and severity are different questions.** "How likely?" (probability) and "how bad if it happens?" (severity, an expected conditional drawdown) are estimated separately, because a low-probability/high-severity risk (e.g., market crash) needs different handling than a high-probability/low-severity one.
- **Estimates are honest and bounded.** We use transparent heuristics + models grounded in historical analogues, and we never present a spuriously precise number without a confidence caveat.
- **Risk feeds product surfaces:** the Investment Score penalty, **bubble/oversupply alerts** ([11](11-ai-features.md)), and the portfolio risk view.

## 2. Risk taxonomy

| Factor | What it is | Primary signals (as-of t) | Probability estimation | Severity (expected drawdown if it hits) |
|--------|------------|----------------------------|------------------------|------------------------------------------|
| **Reprint** | Manufacturer reissues the product | set age, series reprint base rate, current demand/scarcity, official announcements | heuristic + logistic model on historical reprint events | high for modern sealed (supply shock); calibrated from past reprint price drops |
| **Bubble / froth** | Unsustainable hype-driven spike | `rsi_14` overbought, `price_accel`, attention spike vs `ev_to_price`, deviation from trend | rule-blended score → probability via logistic squashing | high (mean-reversion) |
| **Oversupply** | Supply rising faster than demand | `supply_growth_30/90d`, falling `sold_listed_ratio` | monotonic map of supply growth vs demand | medium–high |
| **Liquidity collapse** | Cannot sell without large discount | low turnover, widening spread, thin listing depth | map of `liquidity_score` | medium (realization loss) |
| **Declining demand / collector fatigue** | Interest fading | negative `trends_mom`, falling mentions, aging without new catalysts | trend of attention composite | medium |
| **Market regime / crash** | Broad collectible/discretionary downturn | market index drawdown, `beta_to_market`, macro stress | market-level probability × instrument beta | high, systematic |
| **Macro recession** | Discretionary spend contraction | rates, inflation, consumer sentiment (vintage) | macro model / regime indicator | medium–high |
| **Counterfeit / integrity** | Fakes erode trust/value | category exposure, known-issue flags | mostly categorical prior | variable |
| **Rapid pop growth** (graded classes) | Grading supply dilutes scarcity | PSA/pop growth (when available, Tier 3) | pop growth trend | medium (singles-relevant) |

## 3. Estimating probability

Each factor has a transparent estimator, blending rules with data-driven models where we have labels:

- **Reprint probability** — the flagship example. Features: `months_since_release`, series-level historical reprint frequency, `price_to_msrp` (high premiums attract reprints), demand/attention, and any known reprint announcements. A logistic model is trained on labeled historical reprint events (where available) and blended with a base-rate prior; output ∈ [0,1]. This same value feeds `reprint_probability` in [04](04-feature-engineering.md) and the score penalty in [06](06-investment-score.md).
- **Bubble probability** — a blended rule score: overbought RSI, positive price acceleration, attention spiking while `ev_to_price` says it's already rich, and price far above trend. The blend is squashed to [0,1] via logistic; thresholds tuned on historical froth/collapse episodes and analogues ([09](09-similarity-search.md)).
- **Oversupply / liquidity / demand** — monotonic maps of the relevant supply/liquidity/attention features, anchored to observed distributions.
- **Market/macro** — estimated at the market level (a regime indicator from index drawdown + macro stress) and scaled to the instrument via its `beta_to_market`.

Where labels are thin (early in the project / synthetic era), estimators lean on **base rates + analogues**, and the risk narrative says so.

## 4. Estimating severity

Severity is the **expected conditional loss if the factor materializes** — a fraction ∈ [0,1] (or an expected % drawdown). We estimate it from:

- **Historical shock magnitudes:** e.g., typical price drop after a reprint, or peak-to-trough in past bubbles, drawn from analogues and any real history.
- **Volatility scaling:** severity widens with the instrument's own predicted volatility and interval width ([05](05-machine-learning.md)).
- **Structural factors:** liquidity severity scales with how illiquid the instrument is (a thin market realizes larger losses on exit).

## 5. Aggregation

Per factor `k`, a factor score `r_k = p_k · s_k` (probability × severity), each ∈ [0,1]. The **overall risk** combines them as the probability-weighted chance that *some* material adverse outcome occurs, treating factors as (approximately) independent contributors and avoiding naive summation that could exceed 1:

```
overall_risk = 100 · ( 1 − Π_k (1 − r_k) )
```

This is monotonic (more/worse factors → higher risk), bounded to [0,100], and dominated by the largest factors without being capped by a single one. Correlated factors (e.g., oversupply and declining demand) are optionally grouped so we don't double-count.

Bands:

| Overall risk | Band |
|--------------|------|
| 0–33 | Low |
| 34–66 | Medium |
| 67–100 | High |

## 6. Portfolio-level risk

Beyond per-instrument risk, the engine assesses a **portfolio**:

- **Concentration** — exposure to a single instrument/set/category (Herfindahl-style index); flags over-concentration.
- **Correlation** — instruments in the same set/era co-move; the portfolio's effective diversification is less than its instrument count suggests. We estimate a correlation matrix from returns and report diversification.
- **Factor exposure** — aggregate reprint exposure, bubble exposure, macro beta across holdings.
- **Portfolio VaR / expected shortfall** — via the Monte Carlo engine ([11](11-ai-features.md)), simulating correlated instrument paths.

## 7. Outputs

For each instrument, the engine persists a `risk_assessment` with `overall_risk`, band, and per-factor `risk_factors` rows (probability, severity, score, narrative) ([03 §9](03-database-design.md#9-derived-signals)). These drive:

- The **Investment Score** risk drag and reprint penalty ([06](06-investment-score.md)).
- **Alerts:** bubble warnings, oversupply warnings, liquidity warnings ([11](11-ai-features.md)).
- The product page **Risk panel** and the portfolio **Risk view** ([10](10-ux-design.md)).

## 8. Narratives

Each material factor gets a templated, fact-grounded sentence (optionally LLM-polished under the guardrails of [08](08-explainable-ai.md)):

> *"Reprint risk is elevated (probability ~55%, high severity): this set is 14 months old, trades at 2.3× MSRP, and the series has been reprinted before. A reprint has historically pressured comparable sealed products by 20–35%."*

> *"Bubble risk is moderate: RSI is 74 (overbought) and price has accelerated while intrinsic pack EV lags the current price by 30%."*

## 9. Calibration

Like the score, risk estimates are validated: do high-reprint-risk instruments actually suffer more reprint-driven drawdowns? Do high-bubble-risk items mean-revert more often? We track factor **reliability** (predicted probability vs. observed frequency) and severity **realized vs. expected**, and recalibrate as real events accumulate. Early on, calibration is limited and explicitly caveated.

Continue to [08 — Explainable AI](08-explainable-ai.md).
