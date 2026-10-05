"""Walk-forward (purged) evaluation and forecasting metrics.

Time-series cross-validation must never let the future leak into the past. We use
an expanding-window scheme and *purge* training rows whose forward-return label
would overlap the test window, plus an embargo gap
(docs/05-machine-learning.md - Validation).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Callable, Optional, Protocol

import numpy as np
import pandas as pd

from pokequant.ml.dataset import SupervisedDataset


class SupportsForecast(Protocol):
    def fit_xy(self, X: pd.DataFrame, y: pd.Series) -> None: ...
    def predict_return(self, X: pd.DataFrame) -> np.ndarray: ...
    def predict_quantiles(
        self, X: pd.DataFrame, quantiles: Sequence[float] = ...
    ) -> dict[float, np.ndarray]: ...


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Share of predictions with the correct sign (up vs down)."""
    if y_true.size == 0:
        return float("nan")
    return float(np.mean(np.sign(y_true) == np.sign(y_pred)))


def picp(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Prediction Interval Coverage Probability (share inside [lower, upper])."""
    return float(np.mean((y_true >= lower) & (y_true <= upper)))


def mpiw(lower: np.ndarray, upper: np.ndarray) -> float:
    """Mean Prediction Interval Width."""
    return float(np.mean(upper - lower))


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    lower: Optional[np.ndarray] = None,
    upper: Optional[np.ndarray] = None,
    *,
    last_price: Optional[np.ndarray] = None,
) -> dict[str, float]:
    """Return-scale metrics plus optional price-scale MAPE."""
    metrics: dict[str, float] = {
        "n": float(len(y_true)),
        "rmse": rmse(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "directional_accuracy": directional_accuracy(y_true, y_pred),
    }
    if lower is not None and upper is not None:
        metrics["picp"] = picp(y_true, lower, upper)
        metrics["mpiw"] = mpiw(lower, upper)
    if last_price is not None:
        price_true = last_price * np.exp(y_true)
        price_pred = last_price * np.exp(y_pred)
        metrics["mape"] = float(np.mean(np.abs((price_true - price_pred) / price_true)))
    return metrics


def time_series_folds(
    as_of: pd.Series,
    n_splits: int,
    horizon_days: int,
    embargo_days: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window folds with purge+embargo. Returns (train_idx, test_idx)."""
    values = pd.to_datetime(as_of).to_numpy()
    dates = np.sort(np.unique(values))
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    if len(dates) < (n_splits + 1):
        return folds
    gap = np.timedelta64(horizon_days + embargo_days, "D")
    for i in range(1, n_splits + 1):
        cut = int(len(dates) * i / (n_splits + 1))
        end = int(len(dates) * (i + 1) / (n_splits + 1))
        if cut <= 0 or end <= cut:
            continue
        test_start = dates[cut]
        test_end = dates[end - 1]
        train_mask = values <= (test_start - gap)
        test_mask = (values >= test_start) & (values <= test_end)
        if not train_mask.any() or not test_mask.any():
            continue
        folds.append((np.where(train_mask)[0], np.where(test_mask)[0]))
    return folds


def evaluate_forecaster(
    factory: Callable[[], SupportsForecast],
    ds: SupervisedDataset,
    *,
    n_splits: int = 4,
    quantiles: Sequence[float] = (0.1, 0.5, 0.9),
    embargo_days: int = 5,
) -> dict[str, float]:
    """Run walk-forward CV and return metrics averaged across folds."""
    folds = time_series_folds(ds.as_of, n_splits, ds.horizon_days, embargo_days)
    if not folds:
        return {"n_folds": 0.0}

    lo_q, hi_q = min(quantiles), max(quantiles)
    per_fold: list[dict[str, float]] = []
    for train_idx, test_idx in folds:
        model = factory()
        model.fit_xy(ds.X.iloc[train_idx], ds.y.iloc[train_idx])
        x_test = ds.X.iloc[test_idx]
        y_test = ds.y.iloc[test_idx].to_numpy(dtype=float)
        y_pred = model.predict_return(x_test)
        q = model.predict_quantiles(x_test, quantiles)
        per_fold.append(
            compute_metrics(
                y_test,
                y_pred,
                q[lo_q],
                q[hi_q],
                last_price=ds.last_price.iloc[test_idx].to_numpy(dtype=float),
            )
        )

    keys = {k for fold in per_fold for k in fold}
    agg = {k: float(np.nanmean([f.get(k, np.nan) for f in per_fold])) for k in keys}
    agg["n_folds"] = float(len(per_fold))
    return agg
