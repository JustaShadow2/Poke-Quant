"""Gradient-boosting forecaster with quantile prediction intervals.

Backend is pluggable (docs/adr/0010-quantile-prediction-intervals.md):

* ``lightgbm``  - preferred workhorse (used in the Docker runtime).
* ``sklearn``   - ``HistGradientBoostingRegressor`` fallback that also supports a
  native quantile loss and needs no OpenMP shared library, so the code trains and
  is testable anywhere LightGBM wheels won't load.

We fit one model per quantile and sort predictions per row to prevent quantile
crossing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from pokequant.ml.baselines import DEFAULT_QUANTILES
from pokequant.ml.dataset import SupervisedDataset


def lightgbm_available() -> bool:
    try:
        import lightgbm  # noqa: F401

        return True
    except Exception:
        return False


@dataclass
class GBMConfig:
    n_estimators: int = 400
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_child_samples: int = 20
    subsample: float = 0.8
    colsample: float = 0.8
    l2: float = 1.0
    random_state: int = 42
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES


class GradientBoostingForecaster:
    """Quantile gradient-boosting regressor over the Phase-1 feature set."""

    kind = "gbm"

    def __init__(
        self, config: Optional[GBMConfig] = None, *, backend: Optional[str] = None
    ) -> None:
        self.config = config or GBMConfig()
        self.backend = backend or ("lightgbm" if lightgbm_available() else "sklearn")
        self.feature_names: list[str] = []
        self._models: dict[float, Any] = {}

    # -- construction -----------------------------------------------------
    def _make(self, quantile: float) -> Any:
        c = self.config
        if self.backend == "lightgbm":
            from lightgbm import LGBMRegressor

            return LGBMRegressor(
                objective="quantile",
                alpha=quantile,
                n_estimators=c.n_estimators,
                learning_rate=c.learning_rate,
                num_leaves=c.num_leaves,
                min_child_samples=c.min_child_samples,
                subsample=c.subsample,
                subsample_freq=1,
                colsample_bytree=c.colsample,
                reg_lambda=c.l2,
                random_state=c.random_state,
                n_jobs=-1,
                verbosity=-1,
            )
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(
            loss="quantile",
            quantile=quantile,
            learning_rate=c.learning_rate,
            max_iter=c.n_estimators,
            max_leaf_nodes=c.num_leaves,
            min_samples_leaf=c.min_child_samples,
            l2_regularization=c.l2,
            random_state=c.random_state,
        )

    # -- training ---------------------------------------------------------
    def fit(self, ds: SupervisedDataset) -> None:
        self.fit_xy(ds.X, ds.y)

    def fit_xy(self, X: pd.DataFrame, y: pd.Series) -> None:
        self.feature_names = list(X.columns)
        xv = self._prepare(X)
        yv = np.asarray(y, dtype=float)
        self._models = {}
        for q in self.config.quantiles:
            model = self._make(q)
            model.fit(xv, yv)
            self._models[q] = model

    def _prepare(self, X: pd.DataFrame) -> np.ndarray:
        if self.feature_names:
            X = X[self.feature_names]
        return X.to_numpy(dtype=float)

    # -- inference --------------------------------------------------------
    def _median_q(self) -> float:
        return min(self._models, key=lambda q: abs(q - 0.5))

    def predict_return(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self._models[self._median_q()].predict(self._prepare(X)), dtype=float)

    def predict_quantiles(
        self, X: pd.DataFrame, quantiles: Sequence[float] = DEFAULT_QUANTILES
    ) -> dict[float, np.ndarray]:
        requested = sorted(quantiles)
        missing = [q for q in requested if q not in self._models]
        if missing:
            raise ValueError(f"Model was not trained for quantiles {missing}")
        xv = self._prepare(X)
        stacked = np.vstack([self._models[q].predict(xv) for q in requested])
        stacked = np.sort(stacked, axis=0)  # enforce monotone quantiles (no crossing)
        return {q: stacked[i] for i, q in enumerate(requested)}

    def feature_importance(self) -> Optional[dict[str, float]]:
        model = self._models.get(self._median_q())
        importances = getattr(model, "feature_importances_", None)
        if importances is None:
            return None
        return {n: float(v) for n, v in zip(self.feature_names, importances)}
