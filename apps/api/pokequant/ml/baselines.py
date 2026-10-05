"""Naive baselines - the honesty check every forecasting project needs.

A model that cannot beat "price stays flat" (random walk) or "recent drift
continues" on walk-forward validation is not adding value. Intervals come from
the empirical distribution of in-sample residuals.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from pokequant.ml.dataset import SupervisedDataset

DEFAULT_QUANTILES: tuple[float, ...] = (0.1, 0.5, 0.9)


class BaselineForecaster:
    """Shared residual-interval machinery."""

    kind = "baseline"

    def __init__(self, horizon_days: int) -> None:
        self.horizon_days = horizon_days
        self._residuals: np.ndarray = np.array([])

    def predict_return(self, X: pd.DataFrame) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError

    def fit(self, ds: SupervisedDataset) -> None:
        self.fit_xy(ds.X, ds.y)

    def fit_xy(self, X: pd.DataFrame, y: pd.Series) -> None:
        preds = self.predict_return(X)
        self._residuals = y.to_numpy(dtype=float) - preds

    def predict_quantiles(
        self, X: pd.DataFrame, quantiles: Sequence[float] = DEFAULT_QUANTILES
    ) -> dict[float, np.ndarray]:
        base = self.predict_return(X)
        out: dict[float, np.ndarray] = {}
        for q in quantiles:
            offset = float(np.quantile(self._residuals, q)) if self._residuals.size else 0.0
            out[q] = base + offset
        return out


class NaiveForecaster(BaselineForecaster):
    """Random walk: expected forward return is zero (price stays put)."""

    kind = "naive"

    def predict_return(self, X: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(X), dtype=float)


class DriftForecaster(BaselineForecaster):
    """Random walk with drift: extrapolate the trailing 90-day per-day return."""

    kind = "seasonal_naive"

    def predict_return(self, X: pd.DataFrame) -> np.ndarray:
        if "ret_90" not in X.columns:
            return np.zeros(len(X), dtype=float)
        per_day = X["ret_90"].to_numpy(dtype=float) / 90.0
        return np.nan_to_num(per_day) * self.horizon_days
