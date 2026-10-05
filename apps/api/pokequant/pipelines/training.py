"""DB-backed training pipeline: load histories -> train/register -> record rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from pokequant.core.logging import get_logger
from pokequant.domain.enums import Horizon, ModelStage
from pokequant.ml.dataset import snapshots_to_frame
from pokequant.ml.registry import FileModelRegistry
from pokequant.ml.train import TrainingReport, train_and_register
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import SnapshotRepository
from pokequant.repositories.ml_repo import ModelRepository

log = get_logger(__name__)


def train_models(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
    n_splits: int = 4,
) -> TrainingReport:
    catalog = CatalogRepository(session)
    snapshots = SnapshotRepository(session)
    model_repo = ModelRepository(session)

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

    report = train_and_register(
        histories,
        releases,
        horizon,
        registry,
        asset_class=asset_class,
        n_splits=n_splits,
        data_is_synthetic=synthetic_any,
    )

    model = model_repo.upsert_model(
        name=report.model_name,
        asset_class=asset_class,
        kind="gbm",
        description="Phase 1 gradient-boosting quantile forecaster",
    )
    metrics_blob: dict[str, Any] = dict(report.metrics)
    metrics_blob["beats_naive_rmse"] = report.beats_naive_rmse
    version = model_repo.add_version(
        model_id=model.id,
        version=report.model_version or "unknown",
        horizon=horizon.value,
        backend=report.backend,
        feature_set="phase1.v1",
        artifact_uri=str(registry.root / report.model_name / (report.model_version or "")),
        metrics=metrics_blob,
        trained_on_synthetic=synthetic_any,
        stage=ModelStage.PRODUCTION,
    )
    model_repo.promote(version)
    log.info("training_pipeline_done", **{"summary": report.summary()})
    return report
