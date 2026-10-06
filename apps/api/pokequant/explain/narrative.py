"""Facts-first natural-language explanation generation.

Converts SHAP attributions into human-readable text. This is a template-based
approach (no LLM dependency) that constructs sentences from computed facts.
The explanation never invents information beyond what SHAP reveals.

Design principles (docs/08-explainable-ai.md):
- Guarded: only states what the data shows, no speculation.
- Cites specific feature values and their directional impact.
- Short enough for a UI tooltip; full attributions stored for drill-down.
"""

from __future__ import annotations

from pokequant.explain.shap_explain import Explanation

# Human-readable descriptions for features.
_FEATURE_LABELS: dict[str, str] = {
    "ret_7": "7-day return",
    "ret_30": "30-day return",
    "ret_90": "90-day return",
    "mom_accel": "momentum acceleration",
    "sma_ratio_20": "price vs 20-day average",
    "sma_ratio_50": "price vs 50-day average",
    "ema_ratio_20": "price vs 20-day EMA",
    "rsi_14": "14-day RSI",
    "macd_hist": "MACD momentum",
    "bb_pctb_20": "Bollinger Band position",
    "bb_width_20": "Bollinger Band width (volatility)",
    "vol_30": "30-day volatility",
    "vol_90": "90-day volatility",
    "max_dd_180": "max drawdown (180d)",
    "log_price": "price level",
    "log_active_listings": "active listing count",
    "listings_chg_30": "listing count change (30d)",
    "log_volume_30": "30-day trading volume",
    "attention_index": "search/attention interest",
    "attention_chg_30": "attention trend (30d)",
    "days_since_release": "time since release",
    "months_since_release": "maturity (months since release)",
    "month_sin": "seasonal timing",
    "month_cos": "seasonal timing",
    "is_q4": "Q4 holiday season",
}


def _label(feature: str) -> str:
    return _FEATURE_LABELS.get(feature, feature.replace("_", " "))


def _direction_word(shap_val: float, predicted_return: float) -> str:
    """Describe whether a feature pushes toward or away from the prediction direction."""
    if shap_val > 0:
        return "supports" if predicted_return > 0 else "partially offsets decline with"
    return "drags on" if predicted_return > 0 else "contributes to decline via"


def generate_narrative(explanation: Explanation, *, max_drivers: int = 3) -> str:
    """Generate a one-paragraph natural-language explanation from SHAP attributions.

    Returns a concise (2-4 sentence) explanation suitable for display in the UI's
    WhyPanel component.
    """
    ret = explanation.predicted_return
    direction = "rise" if ret > 0.01 else "decline" if ret < -0.01 else "stay roughly flat"
    pct = abs(ret * 100)

    # Opening sentence.
    lines: list[str] = []
    lines.append(
        f"The model expects this product to {direction} "
        f"({pct:.1f}% over the forecast horizon)."
    )

    # Positive drivers.
    pos = explanation.top_positive[:max_drivers]
    if pos:
        drivers = ", ".join(_label(a.feature) for a in pos)
        lines.append(f"Key factors pushing the forecast up: {drivers}.")

    # Negative drivers.
    neg = explanation.top_negative[:max_drivers]
    if neg:
        drags = ", ".join(_label(a.feature) for a in neg)
        lines.append(f"Factors pulling it down: {drags}.")

    # Confidence qualifier.
    total_abs = sum(a.abs_shap for a in explanation.attributions)
    top_concentration = sum(a.abs_shap for a in (pos + neg))
    if total_abs > 0 and top_concentration / total_abs > 0.6:
        lines.append("The prediction is driven by a few dominant signals.")
    elif total_abs > 0:
        lines.append("The prediction reflects a broad mix of factors.")

    return " ".join(lines)
