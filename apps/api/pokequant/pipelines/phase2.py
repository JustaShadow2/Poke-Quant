"""Phase 2 batch pipeline: explain -> score -> risk for all instruments.

Runs after forecasting completes. For each instrument with a stored prediction:
1. Computes SHAP explanations and persists them.
2. Computes the Investment Score (cross-sectional, all instruments together).
3. Computes the Risk Assessment.

Also provides a conformal calibration step to run after training (before forecasting).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from pokequant.core.clock import today
from pokequant.core.logging import get_logger
from pokequant.domain.enums import Horizon
from pokequant.explain.narrative import generate_narrative
from pokequant.explain.shap_explain import explain_prediction
from pokequant.ml.conformal import CalibrationResult, calibrate, calibration_split
from pokequant.ml.dataset import SupervisedDataset, build_dataset, snapshots_to_frame
from pokequant.ml.forecast import forecast_instrument
from pokequant.ml.gbm import GradientBoostingForecaster
from pokequant.ml.registry import FileModelRegistry
from pokequant.ml.train import model_name_for
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import SnapshotRepository
from pokequant.repositories.ml_repo import ModelRepository, PredictionRepository
from pokequant.repositories.phase2_repo import (
    ExplanationRepository,
    RiskRepository,
    ScoreRepository,
    CalibrationRepository,
)
from pokequant.risk.engine import RiskAssessment, assess_risk, inputs_from_features
from pokequant.scoring.compute import compute_scores_batch, inputs_from_features_and_forecast
from pokequant.scoring.engine import BALANCED_PROFILE

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Conformal calibration (post-training, before forecasting)
# ---------------------------------------------------------------------------


def run_calibration(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
    nominal_coverage: float = 0.90,
) -> Optional[CalibrationResult]:
    """Run conformal calibration on the production model and persist the result.

    Splits the training data temporally: last 20% as calibration set.
    The adjustment is stored both in the file registry metadata and in the DB.
    """
    catalog = CatalogRepository(session)
    snapshots_repo = SnapshotRepository(session)
    model_repo = ModelRepository(session)
    cal_repo = CalibrationRepository(session)

    name = model_name_for(asset_class, horizon)
    version = model_repo.production_version(name, horizon.value)
    if version is None:
        log.warning("no_production_model_for_calibration", model=name)
        return None

    forecaster, card = registry.load(name)
    if not isinstance(forecaster, GradientBoostingForecaster):
        log.warning("calibration_only_supports_gbm")
        return None

    # Build dataset for calibration split.
    histories = {}
    releases = {}
    for inst in catalog.all_active(asset_class):
        records = snapshots_repo.history(inst.id)
        if not records:
            continue
        frame = snapshots_to_frame(records)
        if frame.empty:
            continue
        histories[str(inst.id)] = frame
        releases[str(inst.id)] = inst.release_date or frame.index[0].date()

    ds = build_dataset(histories, releases, horizon.days)
    if len(ds) < 50:
        log.warning("insufficient_data_for_calibration", rows=len(ds))
        return None

    # Temporal split.
    train_X, train_y, cal_X, cal_y = calibration_split(ds.X, ds.y, cal_fraction=0.2)

    # Calibrate.
    lo_q = min(forecaster.config.quantiles)
    hi_q = max(forecaster.config.quantiles)
    result = calibrate(
        forecaster, cal_X, cal_y,
        lo_quantile=lo_q, hi_quantile=hi_q,
        nominal_coverage=nominal_coverage,
    )

    # Persist.
    cal_repo.upsert(
        model_version_id=version.id,
        nominal_coverage=result.nominal_coverage,
        lo_quantile=result.lo_quantile,
        hi_quantile=result.hi_quantile,
        adjustment=result.adjustment,
        coverage_before=result.empirical_coverage_before,
        coverage_after=result.empirical_coverage_after,
        n_calibration=result.n_calibration,
    )

    log.info(
        "calibration_complete",
        model=name,
        coverage_before=round(result.empirical_coverage_before, 3),
        coverage_after=round(result.empirical_coverage_after, 3),
        adjustment=round(result.adjustment, 4),
    )
    return result


# ---------------------------------------------------------------------------
# SHAP explanations (post-forecasting)
# ---------------------------------------------------------------------------


def run_explanations(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
) -> dict[str, int]:
    """Compute and store SHAP explanations for all instruments with predictions."""
    catalog = CatalogRepository(session)
    snapshots_repo = SnapshotRepository(session)
    model_repo = ModelRepository(session)
    predictions_repo = PredictionRepository(session)
    explain_repo = ExplanationRepository(session)

    name = model_name_for(asset_class, horizon)
    version = model_repo.production_version(name, horizon.value)
    if version is None:
        return {"explained": 0, "error": "no_production_model"}

    forecaster, card = registry.load(name)
    if not isinstance(forecaster, GradientBoostingForecaster):
        return {"explained": 0, "error": "not_gbm"}

    from pokequant.features.builder import build_features, FEATURE_NAMES

    explained = 0
    for inst in catalog.all_active(asset_class):
        prediction = predictions_repo.latest(inst.id, horizon.value)
        if prediction is None:
            continue

        records = snapshots_repo.history(inst.id)
        if not records:
            continue
        frame = snapshots_to_frame(records)
        if frame.empty:
            continue

        release = inst.release_date or frame.index[0].date()
        features_df = build_features(frame, release)
        if features_df.empty:
            continue

        # Take last row for explanation.
        X = features_df.iloc[[-1]]

        try:
            explanation = explain_prediction(
                forecaster, X,
                instrument_id=str(inst.id),
                horizon=horizon.value,
                model_version=version.version,
            )
        except Exception as exc:
            log.warning("explain_failed", instrument=str(inst.id), error=str(exc))
            continue

        narrative = generate_narrative(explanation)

        # Build attributions dict for storage.
        attr_dict = {a.feature: a.shap_value for a in explanation.attributions}
        top_pos = [
            {"feature": a.feature, "value": a.value, "shap_value": a.shap_value}
            for a in explanation.top_positive
        ]
        top_neg = [
            {"feature": a.feature, "value": a.value, "shap_value": a.shap_value}
            for a in explanation.top_negative
        ]

        explain_repo.upsert(
            prediction_id=prediction.id,
            instrument_id=inst.id,
            horizon=horizon.value,
            as_of_date=prediction.as_of_date,
            base_value=explanation.base_value,
            attributions=attr_dict,
            top_positive=top_pos,
            top_negative=top_neg,
            narrative=narrative,
            model_version_id=version.id,
        )
        explained += 1

    log.info("explanations_complete", count=explained)
    return {"explained": explained}


# ---------------------------------------------------------------------------
# Investment Scores (post-explanation)
# ---------------------------------------------------------------------------


def run_scores(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
) -> dict[str, int]:
    """Compute and store Investment Scores for all instruments."""
    catalog = CatalogRepository(session)
    snapshots_repo = SnapshotRepository(session)
    model_repo = ModelRepository(session)
    predictions_repo = PredictionRepository(session)
    score_repo = ScoreRepository(session)
    risk_repo = RiskRepository(session)

    from pokequant.features.builder import build_features

    name = model_name_for(asset_class, horizon)
    version = model_repo.production_version(name, horizon.value)

    # Gather data for all instruments.
    instruments_data: list[dict[str, Any]] = []
    instrument_ids: list[uuid.UUID] = []

    for inst in catalog.all_active(asset_class):
        records = snapshots_repo.history(inst.id)
        if not records:
            continue
        frame = snapshots_to_frame(records)
        if frame.empty:
            continue

        release = inst.release_date or frame.index[0].date()
        features_df = build_features(frame, release)
        if features_df.empty:
            continue

        latest_features = features_df.iloc[-1].to_dict()

        # Get forecast return from stored prediction.
        prediction = predictions_repo.latest(inst.id, horizon.value)
        forecast_return = prediction.predicted_return if prediction else None

        # Interval width for confidence.
        interval_width = None
        if prediction and prediction.quantiles:
            ret_q = prediction.quantiles.get("return", {})
            lo = ret_q.get("0.1") or ret_q.get("0.05")
            hi = ret_q.get("0.9") or ret_q.get("0.95")
            if lo is not None and hi is not None:
                interval_width = float(hi) - float(lo)

        # Get risk score (compute inline for scoring).
        risk_inputs = inputs_from_features(
            latest_features,
            price_usd=float(frame["price_usd"].iloc[-1]),
            months_since_release=latest_features.get("months_since_release"),
        )
        risk_result = assess_risk(risk_inputs, instrument_id=str(inst.id), horizon=horizon.value)

        # Store risk assessment.
        risk_repo.upsert(
            instrument_id=inst.id,
            as_of_date=today(),
            horizon=horizon.value,
            overall_score=risk_result.overall_score,
            overall_level=risk_result.overall_level.value,
            factors=[f.to_dict() for f in risk_result.factors],
            narrative=risk_result.narrative,
        )

        instruments_data.append({
            "instrument_id": str(inst.id),
            "features": latest_features,
            "forecast_return": forecast_return,
            "interval_width": interval_width,
            "reprint_risk": next(
                (f.score * 20 for f in risk_result.factors if f.name == "reprint"), 0.0
            ),
            "overall_risk": risk_result.overall_score,
        })
        instrument_ids.append(inst.id)

    if not instruments_data:
        return {"scored": 0}

    # Compute scores cross-sectionally.
    scores = compute_scores_batch(instruments_data, profile=BALANCED_PROFILE, horizon=horizon.value)

    # Persist scores.
    scored = 0
    for score, iid in zip(scores, instrument_ids):
        score_repo.upsert(
            instrument_id=iid,
            as_of_date=today(),
            horizon=horizon.value,
            profile=score.profile,
            score=score.score,
            band=score.band,
            raw_score=score.raw_score,
            components=[
                {"name": c.name, "percentile": c.percentile, "weight": c.weight,
                 "contribution": c.contribution, "direction": c.direction}
                for c in score.components
            ],
            reprint_penalty=score.reprint_penalty,
            risk_penalty=score.risk_penalty,
            data_coverage=score.data_coverage,
            is_sufficient=score.is_sufficient,
            model_version_id=version.id if version else None,
        )
        scored += 1

    log.info("scores_complete", count=scored)
    return {"scored": scored, "risks_assessed": len(instrument_ids)}


# ---------------------------------------------------------------------------
# Full Phase 2 batch (after forecasting)
# ---------------------------------------------------------------------------


def run_phase2_batch(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
) -> dict[str, Any]:
    """Run the full Phase 2 batch: explain -> score (includes risk)."""
    explain_result = run_explanations(session, registry, horizon=horizon, asset_class=asset_class)
    score_result = run_scores(session, registry, horizon=horizon, asset_class=asset_class)
    return {
        "explanations": explain_result,
        "scores": score_result,
    }
