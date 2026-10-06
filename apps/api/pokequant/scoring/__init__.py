"""Investment Score module: the 0-100 composite rating."""

from pokequant.scoring.engine import (
    InvestmentScore,
    ScoreComponent,
    ScoreProfile,
    compute_score,
    BALANCED_PROFILE,
    VALUE_PROFILE,
    MOMENTUM_PROFILE,
    CONSERVATIVE_PROFILE,
)

__all__ = [
    "InvestmentScore",
    "ScoreComponent",
    "ScoreProfile",
    "compute_score",
    "BALANCED_PROFILE",
    "VALUE_PROFILE",
    "MOMENTUM_PROFILE",
    "CONSERVATIVE_PROFILE",
]
