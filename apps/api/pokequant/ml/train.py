"""Training orchestration: build dataset -> benchmark -> refit -> register.

DB-agnostic on purpose: callers pass in per-instrument price histories, so this
runs identically against synthetic data (offline) or real ingested data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import pandas as pd

from pokequant.core.logging import get_logger
from pokequant.domain.enums import Horizon
from pokequant.ml.baselines import DriftForecaster, NaiveForecaster
from pokequant.ml.dataset import build_dataset
from pokequant.ml.evaluate import evaluate_forecaster
from pokequant.ml.gbm import GBMConfig, GradientBoostingForecaster, lightgbm_available
from pokequant.ml.registry import FileModelRegistry, ModelVersion

log = get_logger(__name__)


@dataclass
class TrainingReport:
    model_name: str
    horizon: Horizon
    backend: str
    n_rows: int
    n_instruments: int
    metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    beats_naive_rmse: bool = False
    model_version: Optional[str] = None

    def summary(self) -> str:
        gbm = self.metrics.get("gbm", {})
        return (
            f"{self.model_name} [{self.backend}] rows={self.n_rows} "
            f"rmse={gbm.get('rmse', float('nan')):.4f} "
            f"dir_acc={gbm.get('directional_accuracy', float('nan')):.3f} "
            f"beats_naive={self.beats_naive_rmse} version={self.model_version}"
        )


def model_name_for(asset_class: str, horizon: Horizon) -> str:
    return f"forecaster.{asset_class}.{horizon.value}"


def train_and_register(
    histories: dict[str, pd.DataFrame],
    release_dates: dict[str, date],
    horizon: Horizon,
    registry: FileModelRegistry,
    *,
    asset_class: str = "pokemon",
    n_splits: int = 4,
    gbm_config: Optional[GBMConfig] = None,
    data_is_synthetic: bool = True,
) -> TrainingReport:
    ds = build_dataset(histories, release_dates, horizon.days)
    if len(ds) == 0:
        raise ValueError("No training rows - ingest/generate history first")

    gbm_config = gbm_config or GBMConfig()
    metrics = {
        "naive": evaluate_forecaster(lambda: NaiveForecaster(horizon.days), ds, n_splits=n_splits),
        "drift": evaluate_forecaster(lambda: DriftForecaster(horizon.days), ds, n_splits=n_splits),
        "gbm": evaluate_forecaster(
            lambda: GradientBoostingForecaster(gbm_config), ds, n_splits=n_splits
        ),
    }

    beats = metrics["gbm"].get("rmse", float("inf")) <= metrics["naive"].get("rmse", float("inf"))

    # Refit the production GBM on ALL available rows.
    production = GradientBoostingForecaster(gbm_config)
    production.fit(ds)

    name = model_name_for(asset_class, horizon)
    card: dict[str, Any] = {
        "model_kind": "gbm",
        "backend": production.backend,
        "horizon": horizon.value,
        "horizon_days": horizon.days,
        "asset_class": asset_class,
        "feature_set": "phase1.v1",
        "feature_names": production.feature_names,
        "quantiles": list(gbm_config.quantiles),
        "n_rows": len(ds),
        "n_instruments": int(ds.instrument_id.nunique()),
        "metrics": metrics,
        "beats_naive_rmse": bool(beats),
        "data_is_synthetic": bool(data_is_synthetic),
        "lightgbm_available": lightgbm_available(),
        "notes": (
            "Phase 1 intervals are raw quantile-regression outputs and may be "
            "under-calibrated (see walk-forward PICP). Conformal calibration is "
            "scheduled for Phase 2."
        ),
    }
    version: ModelVersion = registry.save(name, production, card)
    registry.set_production(name, version.version)

    report = TrainingReport(
        model_name=name,
        horizon=horizon,
        backend=production.backend,
        n_rows=len(ds),
        n_instruments=int(ds.instrument_id.nunique()),
        metrics=metrics,
        beats_naive_rmse=bool(beats),
        model_version=version.version,
    )
    log.info("model_trained", **{k: v for k, v in vars(report).items() if k != "metrics"})
    return report
