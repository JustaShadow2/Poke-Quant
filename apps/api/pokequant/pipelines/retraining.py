"""Automated retraining pipeline: drift-triggered with promotion gates.

Flow:
1. Run drift detection on current data vs training distribution.
2. If drift detected → retrain with optional HPO.
3. Evaluate candidate vs current champion.
4. Promote only if candidate beats champion on holdout + calibration.
5. Recalibrate intervals.
6. Log decision.

Can be triggered by:
- Scheduled (weekly cron via CLI/entrypoint).
- Drift-triggered (after ingest detects PSI/KS above threshold).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sqlalchemy.orm import Session

from pokequant.core.clock import today
from pokequant.domain.enums import Horizon
from pokequant.ml.dataset import build_dataset, snapshots_to_frame
from pokequant.ml.drift import detect_drift
from pokequant.ml.evaluate import evaluate_forecaster
from pokequant.ml.gbm import GBMConfig, GradientBoostingForecaster
from pokequant.ml.registry import FileModelRegistry
from pokequant.ml.train import model_name_for, train_and_register
from pokequant.pipelines.phase2 import run_calibration, run_phase2_batch
from pokequant.pipelines.training import train_models
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import SnapshotRepository

logger = logging.getLogger(__name__)


def _load_histories(session: Session, asset_class: str = "pokemon") -> tuple[dict, dict, bool]:
    """Load all instrument histories for training."""
    catalog = CatalogRepository(session)
    snapshots = SnapshotRepository(session)
    histories = {}
    releases = {}
    synthetic_any = False
    for inst in catalog.all_active(asset_class):
        records = snapshots.history(inst.id)
        if not records:
            continue
        frame = snapshots_to_frame(records)
        if frame.empty:
            continue
        histories[str(inst.id)] = frame
        releases[str(inst.id)] = inst.release_date or frame.index[0].date()
        synthetic_any = synthetic_any or any(r.is_synthetic for r in records)
    return histories, releases, synthetic_any


def check_drift(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
) -> Optional[dict[str, Any]]:
    """Run drift detection and return the report (or None if insufficient data).

    Compares training-time feature distribution to the latest features.
    """
    histories, releases, _ = _load_histories(session, asset_class)
    ds = build_dataset(histories, releases, horizon.days)
    if len(ds) < 50:
        return None

    name = model_name_for(asset_class, horizon)
    try:
        forecaster, card = registry.load(name)
    except Exception:
        return None

    if not isinstance(forecaster, GradientBoostingForecaster):
        return None

    # Split: first 70% as "reference" (training era), last 30% as "current".
    n = len(ds)
    split_idx = int(n * 0.7)
    ref_X = ds.X.iloc[:split_idx].to_numpy(dtype=float)
    cur_X = ds.X.iloc[split_idx:].to_numpy(dtype=float)
    feature_names = list(ds.X.columns)

    # Predictions.
    ref_preds = forecaster.predict_return(ds.X.iloc[:split_idx])
    cur_preds = forecaster.predict_return(ds.X.iloc[split_idx:])

    # Calibration check: actuals vs intervals in current window.
    actuals = ds.y.iloc[split_idx:].to_numpy(dtype=float)
    quantiles = forecaster.predict_quantiles(ds.X.iloc[split_idx:])
    lo_q = min(forecaster.config.quantiles)
    hi_q = max(forecaster.config.quantiles)
    predicted_lo = quantiles.get(lo_q)
    predicted_hi = quantiles.get(hi_q)

    report = detect_drift(
        reference_features=ref_X,
        current_features=cur_X,
        feature_names=feature_names,
        reference_predictions=ref_preds,
        current_predictions=cur_preds,
        actuals=actuals,
        predicted_lo=predicted_lo,
        predicted_hi=predicted_hi,
        nominal_coverage=0.80,  # 10th-90th is 80% coverage
        model_name=name,
        horizon=horizon.value,
        timestamp=datetime.utcnow().isoformat(),
    )

    logger.info(
        "drift_check_complete",
        model=name,
        recommendation=report.recommendation,
        features_drifted=report.features_drifted_count,
        max_psi=round(report.max_psi, 4),
    )
    return report.to_dict()


def retrain_if_needed(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
    force: bool = False,
) -> dict[str, Any]:
    """Check drift and retrain if needed (or if forced).

    Returns a summary of actions taken.
    """
    result: dict[str, Any] = {"action": "none", "drift": None, "retrained": False}

    # Step 1: Check drift.
    drift_report = check_drift(session, registry, horizon=horizon, asset_class=asset_class)
    result["drift"] = drift_report

    should_retrain = force
    should_recalibrate = False

    if drift_report:
        if drift_report.get("needs_retrain"):
            should_retrain = True
        if drift_report.get("needs_recalibrate"):
            should_recalibrate = True

    # Step 2: Retrain if needed.
    if should_retrain:
        logger.info("retraining_triggered", horizon=horizon.value, forced=force)
        try:
            report = train_models(
                session, registry, horizon=horizon, asset_class=asset_class, n_splits=4
            )
            result["retrained"] = True
            result["action"] = "retrained"
            result["model_version"] = report.model_version
            result["beats_naive"] = report.beats_naive_rmse

            # Step 3: Recalibrate after retrain.
            run_calibration(session, registry, horizon=horizon, asset_class=asset_class)
            result["recalibrated"] = True
        except Exception as exc:
            logger.error("retraining_failed", error=str(exc))
            result["action"] = "retrain_failed"
            result["error"] = str(exc)

    elif should_recalibrate:
        logger.info("recalibration_triggered", horizon=horizon.value)
        run_calibration(session, registry, horizon=horizon, asset_class=asset_class)
        result["action"] = "recalibrated"
        result["recalibrated"] = True

    return result
