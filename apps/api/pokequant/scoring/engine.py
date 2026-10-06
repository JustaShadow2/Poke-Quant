"""PokéQuant Investment Score — the 0-100 composite rating.

Implements docs/06-investment-score.md: a transparent, decomposable, weighted
composite of 8 reward/confidence sub-scores minus 2 risk penalties. Each raw
signal is converted to a cross-sectional percentile (0-100) within the asset
class, making components comparable and regime-robust.

The score is additive by design: each component's contribution is directly
reportable (w_k * c_k), powering the "why" breakdown in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Profiles (weight configurations)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreProfile:
    """Weight configuration for the Investment Score."""

    name: str
    # Reward + confidence component weights (must sum to 1.0).
    w_expected_return: float
    w_risk_adjusted: float
    w_valuation: float
    w_momentum: float
    w_supply_trend: float
    w_demand_trend: float
    w_liquidity: float
    w_confidence: float
    # Penalty coefficients.
    lambda_reprint: float
    lambda_risk: float

    @property
    def weights(self) -> dict[str, float]:
        return {
            "expected_return": self.w_expected_return,
            "risk_adjusted": self.w_risk_adjusted,
            "valuation": self.w_valuation,
            "momentum": self.w_momentum,
            "supply_trend": self.w_supply_trend,
            "demand_trend": self.w_demand_trend,
            "liquidity": self.w_liquidity,
            "confidence": self.w_confidence,
        }


BALANCED_PROFILE = ScoreProfile(
    name="Balanced",
    w_expected_return=0.22,
    w_risk_adjusted=0.16,
    w_valuation=0.16,
    w_momentum=0.12,
    w_supply_trend=0.14,
    w_demand_trend=0.08,
    w_liquidity=0.06,
    w_confidence=0.06,
    lambda_reprint=0.15,
    lambda_risk=0.15,
)

VALUE_PROFILE = ScoreProfile(
    name="Value",
    w_expected_return=0.18,
    w_risk_adjusted=0.16,
    w_valuation=0.26,
    w_momentum=0.06,
    w_supply_trend=0.14,
    w_demand_trend=0.06,
    w_liquidity=0.06,
    w_confidence=0.08,
    lambda_reprint=0.15,
    lambda_risk=0.12,
)

MOMENTUM_PROFILE = ScoreProfile(
    name="Momentum",
    w_expected_return=0.24,
    w_risk_adjusted=0.12,
    w_valuation=0.08,
    w_momentum=0.24,
    w_supply_trend=0.12,
    w_demand_trend=0.14,
    w_liquidity=0.04,
    w_confidence=0.02,
    lambda_reprint=0.10,
    lambda_risk=0.10,
)

CONSERVATIVE_PROFILE = ScoreProfile(
    name="Conservative",
    w_expected_return=0.16,
    w_risk_adjusted=0.24,
    w_valuation=0.16,
    w_momentum=0.06,
    w_supply_trend=0.14,
    w_demand_trend=0.06,
    w_liquidity=0.10,
    w_confidence=0.08,
    lambda_reprint=0.25,
    lambda_risk=0.25,
)


# ---------------------------------------------------------------------------
# Score components and output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreComponent:
    """One sub-score's contribution to the overall score."""

    name: str
    raw_value: float  # the underlying signal value
    percentile: float  # cross-sectional percentile (0-100)
    weight: float  # the profile weight for this component
    contribution: float  # weight * percentile (the additive piece)
    direction: str  # "positive", "negative", "neutral"


@dataclass
class InvestmentScore:
    """The full computed investment score with breakdown."""

    instrument_id: str
    score: float  # final 0-100 score
    band: str  # A+, A, B, C, D, F
    raw_score: float  # pre-calibration composite
    profile: str  # which weight profile was used
    components: list[ScoreComponent] = field(default_factory=list)
    reprint_penalty: float = 0.0
    risk_penalty: float = 0.0
    data_coverage: float = 1.0  # fraction of components that had real data
    is_sufficient: bool = True  # False if too few components available
    horizon: str = "d90"

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "score": round(self.score, 1),
            "band": self.band,
            "raw_score": round(self.raw_score, 1),
            "profile": self.profile,
            "components": [
                {
                    "name": c.name,
                    "percentile": round(c.percentile, 1),
                    "weight": c.weight,
                    "contribution": round(c.contribution, 1),
                    "direction": c.direction,
                }
                for c in self.components
            ],
            "reprint_penalty": round(self.reprint_penalty, 1),
            "risk_penalty": round(self.risk_penalty, 1),
            "data_coverage": round(self.data_coverage, 2),
            "is_sufficient": self.is_sufficient,
            "horizon": self.horizon,
        }


# ---------------------------------------------------------------------------
# Band mapping
# ---------------------------------------------------------------------------

def _score_to_band(score: float) -> str:
    """Map a 0-100 score to a letter band."""
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Percentile computation
# ---------------------------------------------------------------------------

def _percentile_rank(value: float, all_values: list[float]) -> float:
    """Compute the percentile rank of `value` within `all_values` (0-100)."""
    if not all_values or len(all_values) < 2:
        return 50.0  # default to median if no peers
    arr = np.array(all_values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return 50.0
    # Fraction of values less than or equal to this value.
    rank = float(np.searchsorted(np.sort(arr), value, side="right")) / len(arr)
    return min(100.0, max(0.0, rank * 100.0))


# ---------------------------------------------------------------------------
# Input signals
# ---------------------------------------------------------------------------

@dataclass
class ScoreInputs:
    """Raw signal values for computing the Investment Score.

    Each field corresponds to a component from docs/06-investment-score.md.
    None means the signal is unavailable (component will be excluded).
    """

    # Reward components (raw signal values).
    expected_return: Optional[float] = None  # model median forecast return
    predicted_volatility: Optional[float] = None  # for risk-adjusted return
    valuation_gap: Optional[float] = None  # (fair_value - price) / price
    momentum_90: Optional[float] = None  # 90-day return
    supply_growth_90: Optional[float] = None  # 90d listing growth (negated = bullish)
    demand_momentum: Optional[float] = None  # attention/sentiment composite
    liquidity_score: Optional[float] = None  # turnover/depth proxy
    model_confidence: Optional[float] = None  # inverse interval width

    # Penalties (0-100 scale).
    reprint_risk: float = 0.0  # probability * severity (0-100)
    overall_risk: float = 0.0  # aggregate risk (0-100)


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_score(
    inputs: ScoreInputs,
    peer_inputs: list[ScoreInputs],
    *,
    profile: ScoreProfile = BALANCED_PROFILE,
    instrument_id: str = "",
    horizon: str = "d90",
    min_components: int = 4,
) -> InvestmentScore:
    """Compute the PokéQuant Investment Score for one instrument.

    Args:
        inputs: The target instrument's raw signal values.
        peer_inputs: Raw signals for all peer instruments (for cross-sectional ranking).
        profile: Weight configuration to use.
        instrument_id: For metadata.
        horizon: Forecast horizon used.
        min_components: Minimum number of non-None components required.

    Returns:
        InvestmentScore with full breakdown.
    """
    # Map component names to (target_value, all_peer_values, weight, higher_is_better).
    component_defs: list[tuple[str, Optional[float], list[float], float, bool]] = [
        ("expected_return", inputs.expected_return,
         [p.expected_return for p in peer_inputs if p.expected_return is not None],
         profile.w_expected_return, True),
        ("risk_adjusted",
         (inputs.expected_return / inputs.predicted_volatility
          if inputs.expected_return is not None and inputs.predicted_volatility
          and inputs.predicted_volatility > 0.001 else None),
         [p.expected_return / p.predicted_volatility
          for p in peer_inputs
          if p.expected_return is not None and p.predicted_volatility
          and p.predicted_volatility > 0.001],
         profile.w_risk_adjusted, True),
        ("valuation", inputs.valuation_gap,
         [p.valuation_gap for p in peer_inputs if p.valuation_gap is not None],
         profile.w_valuation, True),
        ("momentum", inputs.momentum_90,
         [p.momentum_90 for p in peer_inputs if p.momentum_90 is not None],
         profile.w_momentum, True),
        ("supply_trend",
         -inputs.supply_growth_90 if inputs.supply_growth_90 is not None else None,
         [-p.supply_growth_90 for p in peer_inputs if p.supply_growth_90 is not None],
         profile.w_supply_trend, True),  # negated: declining supply is bullish
        ("demand_trend", inputs.demand_momentum,
         [p.demand_momentum for p in peer_inputs if p.demand_momentum is not None],
         profile.w_demand_trend, True),
        ("liquidity", inputs.liquidity_score,
         [p.liquidity_score for p in peer_inputs if p.liquidity_score is not None],
         profile.w_liquidity, True),
        ("confidence", inputs.model_confidence,
         [p.model_confidence for p in peer_inputs if p.model_confidence is not None],
         profile.w_confidence, True),
    ]

    components: list[ScoreComponent] = []
    raw_sum = 0.0
    available_count = 0
    total_weight = 0.0

    for name, value, peers, weight, higher_better in component_defs:
        if value is None:
            continue
        available_count += 1
        # Include the target value in the peer set for ranking.
        all_vals = peers + [value]
        pct = _percentile_rank(value, all_vals)
        if not higher_better:
            pct = 100.0 - pct
        contribution = weight * pct
        raw_sum += contribution
        total_weight += weight

        direction = "positive" if pct >= 60 else "negative" if pct <= 40 else "neutral"
        components.append(ScoreComponent(
            name=name,
            raw_value=value,
            percentile=pct,
            weight=weight,
            contribution=contribution,
            direction=direction,
        ))

    # Normalize if not all components available (re-weight to sum to 1).
    if total_weight > 0 and total_weight < 0.99:
        raw_sum = raw_sum / total_weight

    # Apply penalties.
    reprint_pen = profile.lambda_reprint * inputs.reprint_risk
    risk_pen = profile.lambda_risk * inputs.overall_risk
    pq_raw = max(0.0, min(100.0, raw_sum - reprint_pen - risk_pen))

    # Check sufficiency.
    data_coverage = available_count / len(component_defs) if component_defs else 0.0
    is_sufficient = available_count >= min_components

    # Band assignment (no isotonic calibration map yet — that requires realized data).
    band = _score_to_band(pq_raw)

    return InvestmentScore(
        instrument_id=instrument_id,
        score=round(pq_raw, 1),
        band=band,
        raw_score=round(raw_sum, 1),
        profile=profile.name,
        components=components,
        reprint_penalty=reprint_pen,
        risk_penalty=risk_pen,
        data_coverage=data_coverage,
        is_sufficient=is_sufficient,
        horizon=horizon,
    )
