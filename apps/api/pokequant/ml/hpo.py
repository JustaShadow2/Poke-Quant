"""Optuna-based hyperparameter optimization for GBM forecasters.

Uses TPE (Tree-structured Parzen Estimator) sampler with median pruning to
efficiently search the GBM hyperparameter space. The objective is the walk-forward
pinball loss (not a single random split), preventing overfitting to one fold.

The search space follows docs/05-machine-learning.md §6:
- num_leaves: 15-255
- max_depth: -1, 3-12
- learning_rate: log 1e-3 to 0.3
- min_child_samples: 5-200
- subsample/colsample: 0.5-1.0
- l2 regularization: log 1e-3 to 10
- n_estimators: with early stopping consideration

Usage:
    best_config = optimize_gbm(dataset, horizon, n_trials=50)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from pokequant.core.logging import get_logger
from pokequant.ml.dataset import SupervisedDataset
from pokequant.ml.evaluate import evaluate_forecaster
from pokequant.ml.gbm import GBMConfig, GradientBoostingForecaster

log = get_logger(__name__)


@dataclass
class HPOResult:
    """Result from hyperparameter optimization."""

    best_config: GBMConfig
    best_score: float  # walk-forward objective value
    n_trials: int
    study_name: str
    best_params: dict[str, Any]
    all_trials_summary: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_score": round(self.best_score, 6),
            "n_trials": self.n_trials,
            "study_name": self.study_name,
            "best_params": self.best_params,
        }


def _config_from_params(params: dict[str, Any]) -> GBMConfig:
    """Convert Optuna trial params to a GBMConfig."""
    return GBMConfig(
        n_estimators=params["n_estimators"],
        learning_rate=params["learning_rate"],
        num_leaves=params["num_leaves"],
        min_child_samples=params["min_child_samples"],
        subsample=params["subsample"],
        colsample=params["colsample"],
        l2=params["l2"],
    )


def optimize_gbm(
    dataset: SupervisedDataset,
    *,
    n_trials: int = 50,
    n_splits: int = 3,
    objective_metric: str = "rmse",
    timeout: Optional[float] = None,
    study_name: Optional[str] = None,
) -> HPOResult:
    """Run Optuna HPO over GBM hyperparameters.

    Args:
        dataset: The supervised dataset (features + targets).
        n_trials: Number of Optuna trials.
        n_splits: Walk-forward folds for evaluation.
        objective_metric: Metric to minimize ('rmse', 'mae', or 'pinball').
        timeout: Optional time limit in seconds.
        study_name: Name for the Optuna study.

    Returns:
        HPOResult with the best configuration and study summary.
    """
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study_name = study_name or f"gbm_hpo_{objective_metric}"

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=50),
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 255),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 200),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample": trial.suggest_float("colsample", 0.5, 1.0),
            "l2": trial.suggest_float("l2", 1e-3, 10.0, log=True),
        }

        config = _config_from_params(params)

        try:
            metrics = evaluate_forecaster(
                lambda: GradientBoostingForecaster(config),
                dataset,
                n_splits=n_splits,
            )
        except Exception:
            return float("inf")

        score = metrics.get(objective_metric, float("inf"))
        if np.isnan(score) or np.isinf(score):
            return float("inf")

        return float(score)

    sampler = optuna.samplers.TPESampler(seed=42, multivariate=True)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)

    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
    )

    study.optimize(objective, n_trials=n_trials, timeout=timeout)

    # Extract best.
    best_params = study.best_params
    best_config = _config_from_params(best_params)

    # Summarize all trials.
    trials_summary = []
    for t in study.trials:
        if t.state == optuna.trial.TrialState.COMPLETE:
            trials_summary.append({
                "number": t.number,
                "value": round(t.value, 6) if t.value is not None else None,
                "params": t.params,
            })

    result = HPOResult(
        best_config=best_config,
        best_score=study.best_value,
        n_trials=n_trials,
        study_name=study_name,
        best_params=best_params,
        all_trials_summary=sorted(trials_summary, key=lambda x: x.get("value") or float("inf")),
    )

    log.info(
        "hpo_complete",
        study=study_name,
        best_score=round(study.best_value, 6),
        n_trials=n_trials,
        best_params=best_params,
    )

    return result
