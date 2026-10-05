"""Repositories for the model registry tables and predictions."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pokequant.db.models import Model, ModelVersion, Prediction
from pokequant.domain.enums import ModelStage


class ModelRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_model(
        self, name: str, asset_class: str, kind: str, description: Optional[str] = None
    ) -> Model:
        stmt = (
            pg_insert(Model)
            .values(name=name, asset_class=asset_class, kind=kind, description=description)
            .on_conflict_do_update(
                index_elements=[Model.name],
                set_={"asset_class": asset_class, "kind": kind, "description": description},
            )
        )
        self.session.execute(stmt)
        return self.session.execute(select(Model).where(Model.name == name)).scalar_one()

    def add_version(
        self,
        *,
        model_id: uuid.UUID,
        version: str,
        horizon: str,
        backend: str,
        feature_set: str,
        artifact_uri: Optional[str],
        metrics: dict[str, Any],
        trained_on_synthetic: bool,
        stage: ModelStage = ModelStage.NONE,
    ) -> ModelVersion:
        stmt = (
            pg_insert(ModelVersion)
            .values(
                model_id=model_id,
                version=version,
                horizon=horizon,
                backend=backend,
                feature_set=feature_set,
                artifact_uri=artifact_uri,
                metrics=metrics,
                trained_on_synthetic=trained_on_synthetic,
                stage=stage.value,
            )
            .on_conflict_do_update(
                index_elements=[ModelVersion.model_id, ModelVersion.version],
                set_={"metrics": metrics, "artifact_uri": artifact_uri, "stage": stage.value},
            )
        )
        self.session.execute(stmt)
        return self.session.execute(
            select(ModelVersion).where(
                ModelVersion.model_id == model_id, ModelVersion.version == version
            )
        ).scalar_one()

    def promote(self, model_version: ModelVersion) -> None:
        """Mark this version production and archive prior production of same horizon."""
        self.session.execute(
            update(ModelVersion)
            .where(
                ModelVersion.model_id == model_version.model_id,
                ModelVersion.horizon == model_version.horizon,
                ModelVersion.stage == ModelStage.PRODUCTION.value,
                ModelVersion.id != model_version.id,
            )
            .values(stage=ModelStage.ARCHIVED.value)
        )
        model_version.stage = ModelStage.PRODUCTION

    def production_version(self, model_name: str, horizon: str) -> Optional[ModelVersion]:
        stmt = (
            select(ModelVersion)
            .join(Model)
            .where(
                Model.name == model_name,
                ModelVersion.horizon == horizon,
                ModelVersion.stage == ModelStage.PRODUCTION.value,
            )
            .order_by(ModelVersion.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        instrument_id: uuid.UUID,
        model_version_id: uuid.UUID,
        horizon: str,
        as_of_date: date,
        last_price: Decimal,
        predicted_price: Decimal,
        predicted_return: float,
        quantiles: dict[str, Any],
        is_synthetic: bool,
    ) -> None:
        stmt = pg_insert(Prediction).values(
            instrument_id=instrument_id,
            model_version_id=model_version_id,
            horizon=horizon,
            as_of_date=as_of_date,
            last_price=last_price,
            predicted_price=predicted_price,
            predicted_return=predicted_return,
            quantiles=quantiles,
            is_synthetic=is_synthetic,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                Prediction.instrument_id,
                Prediction.model_version_id,
                Prediction.horizon,
                Prediction.as_of_date,
            ],
            set_={
                "last_price": stmt.excluded.last_price,
                "predicted_price": stmt.excluded.predicted_price,
                "predicted_return": stmt.excluded.predicted_return,
                "quantiles": stmt.excluded.quantiles,
                "is_synthetic": stmt.excluded.is_synthetic,
            },
        )
        self.session.execute(stmt)

    def latest(self, instrument_id: uuid.UUID, horizon: str) -> Optional[Prediction]:
        stmt = (
            select(Prediction)
            .where(Prediction.instrument_id == instrument_id, Prediction.horizon == horizon)
            .order_by(Prediction.as_of_date.desc(), Prediction.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()
