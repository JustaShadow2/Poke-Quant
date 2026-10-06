"""PSA-submission expected-value calculator.

Compares selling raw today vs submitting to PSA (fees + shipping) under a
probability mix of PSA 10 / 9 / 8-or-lower. Probabilities are either conservative
priors or conditioned on the vision pre-grade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DEFAULT_GRADING_FEE = 25.0
DEFAULT_SHIPPING = 15.0

# Unconditional priors for a card the submitter believes is NM. Conservative on purpose.
_PRIOR = (0.18, 0.42, 0.40)  # p10, p9, p8-


def _clamp_probs(p10: float, p9: float, p8: float) -> tuple[float, float, float]:
    total = p10 + p9 + p8
    if total <= 0:
        return _PRIOR
    return p10 / total, p9 / total, p8 / total


def probs_from_predicted_grade(predicted: Optional[float]) -> tuple[float, float, float]:
    """Map a 1-10 predicted grade into (P10, P9, P8-)."""
    if predicted is None:
        return _PRIOR
    g = max(6.0, min(10.0, predicted))
    if g >= 9.7:
        return _clamp_probs(0.58, 0.32, 0.10)
    if g >= 9.3:
        return _clamp_probs(0.38, 0.44, 0.18)
    if g >= 8.8:
        return _clamp_probs(0.16, 0.54, 0.30)
    if g >= 8.2:
        return _clamp_probs(0.06, 0.34, 0.60)
    return _clamp_probs(0.02, 0.18, 0.80)


@dataclass(frozen=True)
class GradeROI:
    raw_usd: float
    psa9_usd: float
    psa10_usd: float
    psa8_usd: float
    grading_fee_usd: float
    shipping_usd: float
    all_in_cost_usd: float
    p10: float
    p9: float
    p8: float
    expected_grade_proceeds: float
    expected_net_vs_raw: float
    breakeven_p10: Optional[float]
    verdict: str
    rationale: str
    prices_are_estimated: bool
    probs_source: str


def _verdict(net: float) -> tuple[str, str]:
    if net >= 25:
        return (
            "grade",
            "Expected proceeds after fees beat selling raw by a meaningful margin.",
        )
    if net >= 5:
        return (
            "borderline",
            "Slightly EV-positive after fees — sensitive to actual PSA 10 rate and comps.",
        )
    if net >= -10:
        return (
            "lean_raw",
            "Close to break-even. Selling raw is simpler unless you believe this copy is a 10.",
        )
    return (
        "sell_raw",
        "Fees eat the grade premium. Selling raw is the better default.",
    )


def breakeven_psa10_rate(
    raw: float,
    psa9: float,
    psa10: float,
    psa8: float,
    all_in: float,
    p9_given_not_10: float = 0.55,
) -> Optional[float]:
    """P(PSA 10) needed so EV = raw, holding the 9 vs 8- mix among non-10s."""
    # EV = p10*10 + (1-p10)*[q*9 + (1-q)*8] - all_in  == raw
    q = p9_given_not_10
    blend = q * psa9 + (1.0 - q) * psa8
    denom = psa10 - blend
    if abs(denom) < 1e-6:
        return None
    p = (raw + all_in - blend) / denom
    if p < 0 or p > 1:
        return None
    return p


def compute_roi(
    *,
    raw_usd: float,
    psa9_usd: float,
    psa10_usd: float,
    psa8_usd: Optional[float] = None,
    grading_fee_usd: float = DEFAULT_GRADING_FEE,
    shipping_usd: float = DEFAULT_SHIPPING,
    predicted_grade: Optional[float] = None,
    prices_are_estimated: bool = True,
) -> GradeROI:
    psa8 = psa8_usd if psa8_usd is not None else max(raw_usd * 0.9, raw_usd)
    all_in = grading_fee_usd + shipping_usd
    p10, p9, p8 = probs_from_predicted_grade(predicted_grade)
    proceeds = p10 * psa10_usd + p9 * psa9_usd + p8 * psa8
    net = proceeds - all_in - raw_usd
    verdict, rationale = _verdict(net)
    be = breakeven_psa10_rate(raw_usd, psa9_usd, psa10_usd, psa8, all_in)
    source = "vision_conditioned" if predicted_grade is not None else "unconditional_prior"
    return GradeROI(
        raw_usd=round(raw_usd, 2),
        psa9_usd=round(psa9_usd, 2),
        psa10_usd=round(psa10_usd, 2),
        psa8_usd=round(psa8, 2),
        grading_fee_usd=round(grading_fee_usd, 2),
        shipping_usd=round(shipping_usd, 2),
        all_in_cost_usd=round(all_in, 2),
        p10=round(p10, 4),
        p9=round(p9, 4),
        p8=round(p8, 4),
        expected_grade_proceeds=round(proceeds, 2),
        expected_net_vs_raw=round(net, 2),
        breakeven_p10=None if be is None else round(be, 4),
        verdict=verdict,
        rationale=rationale,
        prices_are_estimated=prices_are_estimated,
        probs_source=source,
    )
