"""Conformalized Quantile Regression (CQR) for calibrated prediction intervals.

Raw quantile-regression intervals from GBM are typically under/over-calibrated.
CQR (Romano et al., 2019) wraps them with a conformal correction computed on a
held-out calibration set so that empirical coverage matches the nominal level
with finite-sample guarantees.

Usage:
    1. Split data into train + calibration sets.
    2. Train the quantile model on the train set.
    3. Compute nonconformity scores on the calibration set.
    4. At inference, adjust intervals by the conformal quantile of residuals.

The calibration state (sorted residuals + adjustment) is serialized alongside
the model for reproducible inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from pokequant.ml.gbm import GradientBoostingForecaster


@dataclass
class CalibrationResult:
    """Result of conformal calibration on a held-out set."""

    nominal_coverage: float  # target coverage (e.g., 0.9)
    lo_quantile: float  # lower quantile used (e.g., 0.05)
    hi_quantile: float  # upper quantile used (e.g., 0.95)
    adjustment: float  # the conformal correction (added to intervals)
    empirical_coverage_before: float  # raw interval coverage on cal set
    empirical_coverage_after: float  # coverage after adjustment
    n_calibration: int  # size of calibration set
    residuals_sorted: list[float] = field(default_factory=list)  # for storage

    def to_dict(self) -> dict[str, Any]:
        return {
            "nominal_coverage": self.nominal_coverage,
            "lo_quantile": self.lo_quantile,
            "hi_quantile": self.hi_quantile,
            "adjustment": round(self.adjustment, 6),
            "empirical_coverage_before": round(self.empirical_coverage_before, 4),
            "empirical_coverage_after": round(self.empirical_coverage_after, 4),
            "n_calibration": self.n_calibration,
        }


def compute_nonconformity_scores(
    y_true: np.ndarray,
    q_lo: np.ndarray,
    q_hi: np.ndarray,
) -> np.ndarray:
    """Compute CQR nonconformity scores.

    Score = max(q_lo - y, y - q_hi). Negative means inside the interval.
    """
    return np.maximum(q_lo - y_true, y_true - q_hi)


def calibrate(
    forecaster: GradientBoostingForecaster,
    X_cal: pd.DataFrame,
    y_cal: pd.Series,
    *,
    lo_quantile: float = 0.05,
    hi_quantile: float = 0.95,
    nominal_coverage: float = 0.90,
) -> CalibrationResult:
    """Run conformal calibration on a held-out calibration set.

    Args:
        forecaster: Trained GBM forecaster (must have lo_quantile and hi_quantile models).
        X_cal: Feature matrix for calibration set.
        y_cal: True targets for calibration set.
        lo_quantile: Lower quantile (default 0.05 for 90% interval).
        hi_quantile: Upper quantile (default 0.95 for 90% interval).
        nominal_coverage: Desired coverage level (default 0.90).

    Returns:
        CalibrationResult with the computed adjustment.
    """
    quantile_preds = forecaster.predict_quantiles(X_cal, quantiles=[lo_quantile, hi_quantile])
    q_lo = quantile_preds[lo_quantile]
    q_hi = quantile_preds[hi_quantile]
    y = np.asarray(y_cal, dtype=float)

    # Empirical coverage before adjustment.
    inside_before = ((y >= q_lo) & (y <= q_hi)).mean()

    # Nonconformity scores.
    scores = compute_nonconformity_scores(y, q_lo, q_hi)
    sorted_scores = np.sort(scores)

    # Conformal quantile: the (1 - alpha)(1 + 1/n)-th quantile of scores.
    n = len(scores)
    alpha = 1.0 - nominal_coverage
    conformal_level = min((1 - alpha) * (1 + 1 / n), 1.0)
    idx = int(np.ceil(conformal_level * n)) - 1
    idx = min(idx, n - 1)
    adjustment = float(sorted_scores[idx])

    # Empirical coverage after adjustment.
    adjusted_lo = q_lo - adjustment
    adjusted_hi = q_hi + adjustment
    inside_after = ((y >= adjusted_lo) & (y <= adjusted_hi)).mean()

    return CalibrationResult(
        nominal_coverage=nominal_coverage,
        lo_quantile=lo_quantile,
        hi_quantile=hi_quantile,
        adjustment=adjustment,
        empirical_coverage_before=float(inside_before),
        empirical_coverage_after=float(inside_after),
        n_calibration=n,
        residuals_sorted=sorted_scores.tolist(),
    )


def apply_conformal_adjustment(
    quantiles: dict[float, np.ndarray],
    calibration: CalibrationResult,
) -> dict[float, np.ndarray]:
    """Apply the conformal adjustment to widen raw quantile intervals.

    Adjusts the lower quantile down and the upper quantile up by the stored
    conformal correction. Interior quantiles (e.g., 0.5 median) are unchanged.
    """
    adjusted = {}
    for q, vals in quantiles.items():
        if q <= calibration.lo_quantile:
            adjusted[q] = vals - calibration.adjustment
        elif q >= calibration.hi_quantile:
            adjusted[q] = vals + calibration.adjustment
        else:
            adjusted[q] = vals
    return adjusted


def calibration_split(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    cal_fraction: float = 0.2,
    temporal: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Split data into training and calibration sets.

    For temporal data, takes the last `cal_fraction` rows as calibration
    (preserving time ordering). For non-temporal, uses a random split.
    """
    n = len(X)
    n_cal = max(10, int(n * cal_fraction))

    if temporal:
        # Last portion for calibration (most recent data).
        train_X = X.iloc[:-n_cal]
        train_y = y.iloc[:-n_cal]
        cal_X = X.iloc[-n_cal:]
        cal_y = y.iloc[-n_cal:]
    else:
        rng = np.random.default_rng(42)
        indices = rng.permutation(n)
        cal_idx = indices[:n_cal]
        train_idx = indices[n_cal:]
        train_X = X.iloc[train_idx]
        train_y = y.iloc[train_idx]
        cal_X = X.iloc[cal_idx]
        cal_y = y.iloc[cal_idx]

    return train_X, train_y, cal_X, cal_y
