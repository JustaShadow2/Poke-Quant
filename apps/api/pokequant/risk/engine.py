"""Risk Engine: probability x severity risk assessment per instrument.

Implements docs/07-risk-engine.md: evaluates 5 risk factors (reprint, bubble,
oversupply, illiquidity, macro), each scored with probability (0-1) and severity
(1-5). The overall risk is a weighted composite. Each factor includes a
natural-language narrative explaining why it triggered.

Risk taxonomy:
- REPRINT: manufacturer reissues the product, pressuring price
- BUBBLE: price disconnected from fundamentals (overheated)
- OVERSUPPLY: too many listings relative to demand
- ILLIQUIDITY: thin market, wide spreads, hard to exit
- MACRO: external economic headwinds (rates, inflation, consumer confidence)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class RiskFactor:
    """A single risk factor assessment."""

    name: str
    probability: float  # 0.0 - 1.0
    severity: int  # 1-5
    score: float  # probability * severity (0-5)
    level: RiskLevel
    narrative: str  # human-readable explanation
    data_driven: bool = True  # False if heuristic/assumed

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "probability": round(self.probability, 2),
            "severity": self.severity,
            "score": round(self.score, 2),
            "level": self.level.value,
            "narrative": self.narrative,
            "data_driven": self.data_driven,
        }


@dataclass
class RiskAssessment:
    """Complete risk assessment for one instrument."""

    instrument_id: str
    overall_score: float  # 0-100 composite risk score
    overall_level: RiskLevel
    factors: list[RiskFactor] = field(default_factory=list)
    narrative: str = ""
    horizon: str = "d90"

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "overall_score": round(self.overall_score, 1),
            "overall_level": self.overall_level.value,
            "factors": [f.to_dict() for f in self.factors],
            "narrative": self.narrative,
            "horizon": self.horizon,
        }


# ---------------------------------------------------------------------------
# Risk factor computation
# ---------------------------------------------------------------------------


@dataclass
class RiskInputs:
    """Raw data inputs for risk assessment."""

    # Price / technical.
    price_usd: float = 0.0
    ret_90: Optional[float] = None  # 90-day return
    vol_30: Optional[float] = None  # 30-day realized volatility
    vol_90: Optional[float] = None  # 90-day realized volatility
    rsi_14: Optional[float] = None  # RSI
    bb_pctb_20: Optional[float] = None  # Bollinger %B
    max_dd_180: Optional[float] = None  # max drawdown 180d
    sma_ratio_50: Optional[float] = None  # price / SMA50

    # Supply / demand.
    active_listings: Optional[int] = None
    listings_chg_30: Optional[float] = None  # 30d listing growth
    log_volume_30: Optional[float] = None  # trading volume
    attention_index: Optional[float] = None
    attention_chg_30: Optional[float] = None

    # Lifecycle.
    months_since_release: Optional[float] = None
    is_limited_print: bool = False  # known limited run
    is_reprinted: bool = False  # already been reprinted once

    # Macro.
    macro_rates_rising: bool = False
    consumer_confidence_low: bool = False


def _level_from_score(score: float) -> RiskLevel:
    """Map a factor score (0-5) to a risk level."""
    if score < 1.0:
        return RiskLevel.LOW
    if score < 2.5:
        return RiskLevel.MODERATE
    if score < 4.0:
        return RiskLevel.HIGH
    return RiskLevel.VERY_HIGH


def _assess_reprint(inputs: RiskInputs) -> RiskFactor:
    """Evaluate reprint risk."""
    prob = 0.15  # base probability for any sealed product

    # Higher for recent releases (more likely to be reprinted).
    if inputs.months_since_release is not None:
        if inputs.months_since_release < 12:
            prob = 0.45
        elif inputs.months_since_release < 24:
            prob = 0.30
        elif inputs.months_since_release > 48:
            prob = 0.05

    # Already reprinted once → higher chance of another.
    if inputs.is_reprinted:
        prob = min(prob + 0.15, 0.9)

    # Limited print runs are safer.
    if inputs.is_limited_print:
        prob = max(prob - 0.20, 0.02)

    # Severity: reprints typically cause 20-50% drops.
    severity = 4 if prob > 0.3 else 3

    score = prob * severity

    # Narrative.
    if prob > 0.35:
        narrative = (
            "Elevated reprint risk. Recent releases are frequently reprinted, "
            "which historically causes 20-40% price declines."
        )
    elif prob > 0.15:
        narrative = "Moderate reprint probability based on product age and print history."
    else:
        narrative = "Low reprint risk due to product maturity or limited-print status."

    return RiskFactor(
        name="reprint",
        probability=prob,
        severity=severity,
        score=score,
        level=_level_from_score(score),
        narrative=narrative,
        data_driven=inputs.months_since_release is not None,
    )


def _assess_bubble(inputs: RiskInputs) -> RiskFactor:
    """Evaluate bubble / overheating risk."""
    prob = 0.1  # base

    signals = 0
    reasons: list[str] = []

    # RSI overbought.
    if inputs.rsi_14 is not None and inputs.rsi_14 > 75:
        signals += 1
        prob += 0.20
        reasons.append(f"RSI at {inputs.rsi_14:.0f} (overbought)")

    # Bollinger %B above 1 (price above upper band).
    if inputs.bb_pctb_20 is not None and inputs.bb_pctb_20 > 1.0:
        signals += 1
        prob += 0.15
        reasons.append("price above upper Bollinger Band")

    # Extreme 90-day run-up.
    if inputs.ret_90 is not None and inputs.ret_90 > 0.5:
        signals += 1
        prob += 0.20
        reasons.append(f"90-day return of {inputs.ret_90 * 100:.0f}%")

    # Price far above SMA50.
    if inputs.sma_ratio_50 is not None and inputs.sma_ratio_50 > 1.4:
        signals += 1
        prob += 0.10
        reasons.append("price 40%+ above 50-day average")

    prob = min(prob, 0.95)
    severity = min(5, 2 + signals)
    score = prob * severity

    if reasons:
        narrative = f"Bubble signals detected: {'; '.join(reasons)}."
    else:
        narrative = "No significant overheating signals detected."

    return RiskFactor(
        name="bubble",
        probability=prob,
        severity=severity,
        score=score,
        level=_level_from_score(score),
        narrative=narrative,
        data_driven=any([inputs.rsi_14, inputs.bb_pctb_20, inputs.ret_90]),
    )


def _assess_oversupply(inputs: RiskInputs) -> RiskFactor:
    """Evaluate oversupply risk (too many listings vs demand)."""
    prob = 0.1

    reasons: list[str] = []

    # Listings growing rapidly.
    if inputs.listings_chg_30 is not None and inputs.listings_chg_30 > 0.2:
        prob += 0.25
        reasons.append(f"listings up {inputs.listings_chg_30 * 100:.0f}% in 30d")

    # High absolute listings with declining attention.
    if (inputs.attention_chg_30 is not None and inputs.attention_chg_30 < -5
            and inputs.active_listings is not None and inputs.active_listings > 100):
        prob += 0.20
        reasons.append("demand declining while supply grows")

    prob = min(prob, 0.90)
    severity = 3 if prob > 0.3 else 2
    score = prob * severity

    if reasons:
        narrative = f"Oversupply pressure: {'; '.join(reasons)}."
    else:
        narrative = "Supply/demand balance appears healthy."

    return RiskFactor(
        name="oversupply",
        probability=prob,
        severity=severity,
        score=score,
        level=_level_from_score(score),
        narrative=narrative,
        data_driven=inputs.listings_chg_30 is not None,
    )


def _assess_illiquidity(inputs: RiskInputs) -> RiskFactor:
    """Evaluate illiquidity risk (hard to exit position)."""
    prob = 0.2  # collectibles are inherently less liquid

    reasons: list[str] = []

    # Very few listings.
    if inputs.active_listings is not None and inputs.active_listings < 10:
        prob += 0.30
        reasons.append(f"only {inputs.active_listings} active listings")

    # Low volume.
    if inputs.log_volume_30 is not None and inputs.log_volume_30 < 1.0:
        prob += 0.20
        reasons.append("very low trading volume")

    # High volatility implies wide effective spreads.
    if inputs.vol_30 is not None and inputs.vol_30 > 0.3:
        prob += 0.10
        reasons.append("high volatility widens effective spreads")

    prob = min(prob, 0.95)
    severity = 3 if prob > 0.4 else 2
    score = prob * severity

    if reasons:
        narrative = f"Liquidity concerns: {'; '.join(reasons)}."
    else:
        narrative = "Adequate market liquidity for this product."

    return RiskFactor(
        name="illiquidity",
        probability=prob,
        severity=severity,
        score=score,
        level=_level_from_score(score),
        narrative=narrative,
        data_driven=inputs.active_listings is not None or inputs.log_volume_30 is not None,
    )


def _assess_macro(inputs: RiskInputs) -> RiskFactor:
    """Evaluate macro risk (external economic headwinds)."""
    prob = 0.15  # baseline: macro always matters somewhat for discretionary spending

    reasons: list[str] = []

    if inputs.macro_rates_rising:
        prob += 0.15
        reasons.append("rising interest rates pressure discretionary spending")

    if inputs.consumer_confidence_low:
        prob += 0.15
        reasons.append("consumer confidence below trend")

    prob = min(prob, 0.80)
    severity = 2  # macro is a slow headwind, not a sudden crash
    score = prob * severity

    if reasons:
        narrative = f"Macro headwinds: {'; '.join(reasons)}."
    else:
        narrative = "No significant macro headwinds detected."

    return RiskFactor(
        name="macro",
        probability=prob,
        severity=severity,
        score=score,
        level=_level_from_score(score),
        narrative=narrative,
        data_driven=False,  # until FRED data is wired in
    )


# ---------------------------------------------------------------------------
# Main assessment function
# ---------------------------------------------------------------------------

# Factor weights for the overall composite (sum to 1).
_FACTOR_WEIGHTS = {
    "reprint": 0.30,
    "bubble": 0.25,
    "oversupply": 0.20,
    "illiquidity": 0.15,
    "macro": 0.10,
}


def assess_risk(
    inputs: RiskInputs,
    *,
    instrument_id: str = "",
    horizon: str = "d90",
) -> RiskAssessment:
    """Run the full risk assessment for one instrument.

    Returns an assessment with 5 factors, an overall score (0-100), and a
    composite narrative.
    """
    factors = [
        _assess_reprint(inputs),
        _assess_bubble(inputs),
        _assess_oversupply(inputs),
        _assess_illiquidity(inputs),
        _assess_macro(inputs),
    ]

    # Overall score: weighted sum of factor scores, scaled to 0-100.
    # Max possible factor score = 5.0. Scale so that 5.0 → 100.
    weighted_sum = sum(
        f.score * _FACTOR_WEIGHTS.get(f.name, 0.1) for f in factors
    )
    overall = min(100.0, weighted_sum * 20.0)  # 5.0 weighted → 100

    # Overall level.
    if overall < 25:
        level = RiskLevel.LOW
    elif overall < 50:
        level = RiskLevel.MODERATE
    elif overall < 75:
        level = RiskLevel.HIGH
    else:
        level = RiskLevel.VERY_HIGH

    # Composite narrative.
    high_factors = [f for f in factors if f.level in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)]
    if high_factors:
        names = ", ".join(f.name for f in high_factors)
        narrative = f"Elevated risk from: {names}. " + " ".join(f.narrative for f in high_factors)
    elif overall > 40:
        narrative = "Moderate overall risk. No single factor is critical but multiple are elevated."
    else:
        narrative = "Low overall risk profile. No major red flags detected."

    return RiskAssessment(
        instrument_id=instrument_id,
        overall_score=overall,
        overall_level=level,
        factors=factors,
        narrative=narrative,
        horizon=horizon,
    )


def inputs_from_features(
    features: dict[str, float],
    *,
    price_usd: float = 0.0,
    months_since_release: Optional[float] = None,
    active_listings: Optional[int] = None,
    is_limited_print: bool = False,
    is_reprinted: bool = False,
) -> RiskInputs:
    """Build RiskInputs from a feature vector dict.

    Convenience adapter between the feature store and the risk engine.
    """
    return RiskInputs(
        price_usd=price_usd,
        ret_90=features.get("ret_90"),
        vol_30=features.get("vol_30"),
        vol_90=features.get("vol_90"),
        rsi_14=features.get("rsi_14"),
        bb_pctb_20=features.get("bb_pctb_20"),
        max_dd_180=features.get("max_dd_180"),
        sma_ratio_50=features.get("sma_ratio_50"),
        active_listings=active_listings,
        listings_chg_30=features.get("listings_chg_30"),
        log_volume_30=features.get("log_volume_30"),
        attention_index=features.get("attention_index"),
        attention_chg_30=features.get("attention_chg_30"),
        months_since_release=months_since_release or features.get("months_since_release"),
        is_limited_print=is_limited_print,
        is_reprinted=is_reprinted,
    )
