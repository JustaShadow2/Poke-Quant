"""Score computation service: builds ScoreInputs from DB data and computes scores.

This bridges the raw DB/feature/forecast data with the scoring engine. It reads
the latest features, forecasts, and risk assessments to assemble ScoreInputs for
each instrument, then computes scores cross-sectionally.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from pokequant.scoring.engine import (
    BALANCED_PROFILE,
    InvestmentScore,
    ScoreInputs,
    ScoreProfile,
    compute_score,
)


def inputs_from_features_and_forecast(
    features: dict[str, float],
    forecast_return: Optional[float] = None,
    interval_width: Optional[float] = None,
    reprint_risk: float = 0.0,
    overall_risk: float = 0.0,
) -> ScoreInputs:
    """Construct ScoreInputs from a feature vector and forecast result.

    This is the adapter between the feature store / forecast pipeline and the
    scoring engine. Maps specific feature names to score input fields.
    """
    # Expected return from forecast.
    expected_return = forecast_return

    # Predicted volatility from features.
    predicted_vol = features.get("vol_90") or features.get("vol_30")

    # Valuation gap: approximate from price vs SMA (a simple fair-value proxy).
    # In a full implementation this would use a proper fair-value model.
    sma_ratio = features.get("sma_ratio_50")
    valuation_gap: Optional[float] = None
    if sma_ratio is not None and sma_ratio > 0:
        # If price < SMA_50, undervalued (positive gap).
        valuation_gap = (1.0 / sma_ratio) - 1.0

    # Momentum.
    momentum_90 = features.get("ret_90")

    # Supply trend: listings change over 30 days.
    supply_growth = features.get("listings_chg_30")

    # Demand momentum: attention change.
    demand = features.get("attention_chg_30")

    # Liquidity: log volume as a proxy.
    liquidity = features.get("log_volume_30")

    # Model confidence: inverse of interval width (narrower = more confident).
    confidence: Optional[float] = None
    if interval_width is not None and interval_width > 0:
        confidence = 1.0 / interval_width

    return ScoreInputs(
        expected_return=expected_return,
        predicted_volatility=predicted_vol,
        valuation_gap=valuation_gap,
        momentum_90=momentum_90,
        supply_growth_90=supply_growth,
        demand_momentum=demand,
        liquidity_score=liquidity,
        model_confidence=confidence,
        reprint_risk=reprint_risk,
        overall_risk=overall_risk,
    )


def compute_scores_batch(
    instruments_data: list[dict[str, Any]],
    *,
    profile: ScoreProfile = BALANCED_PROFILE,
    horizon: str = "d90",
) -> list[InvestmentScore]:
    """Compute Investment Scores for a batch of instruments.

    Args:
        instruments_data: List of dicts, each with keys:
            - instrument_id: str
            - features: dict[str, float]
            - forecast_return: Optional[float]
            - interval_width: Optional[float]
            - reprint_risk: float (0-100)
            - overall_risk: float (0-100)
        profile: Scoring profile to use.
        horizon: Forecast horizon.

    Returns:
        List of InvestmentScore objects.
    """
    # Build all inputs first (for cross-sectional ranking).
    all_inputs: list[tuple[str, ScoreInputs]] = []
    for item in instruments_data:
        inp = inputs_from_features_and_forecast(
            features=item.get("features", {}),
            forecast_return=item.get("forecast_return"),
            interval_width=item.get("interval_width"),
            reprint_risk=item.get("reprint_risk", 0.0),
            overall_risk=item.get("overall_risk", 0.0),
        )
        all_inputs.append((item["instrument_id"], inp))

    # Extract peer inputs for cross-sectional ranking.
    peer_inputs = [inp for _, inp in all_inputs]

    # Compute scores.
    scores: list[InvestmentScore] = []
    for instrument_id, inputs in all_inputs:
        score = compute_score(
            inputs,
            peer_inputs,
            profile=profile,
            instrument_id=instrument_id,
            horizon=horizon,
        )
        scores.append(score)

    return scores
