"""Forecast read/compute service.

Returns a persisted prediction when one exists (the fast path populated by the
batch forecasting pipeline), otherwise computes one on demand from the current
production model. Both paths yield the same `ForecastView`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional

from pokequant.db.models import Instrument, Prediction
from pokequant.domain.enums import Horizon
from pokequant.ml.dataset import snapshots_to_frame
from pokequant.ml.forecast import forecast_instrument
from pokequant.ml.registry import FileModelRegistry
from pokequant.ml.train import model_name_for
from pokequant.repositories.market import SnapshotRepository
from pokequant.repositories.ml_repo import ModelRepository
from pokequant.repositories.ports import PredictionRepositoryPort


@dataclass
class ForecastView:
    instrument_id: uuid.UUID
    horizon: Horizon
    as_of: date
    last_price: float
    predicted_price: float
    predicted_return: float
    expected_change_pct: float
    quantiles_price: dict[str, float]
    quantiles_return: dict[str, float]
    model_version: Optional[str]
    is_synthetic: bool
    source: str  # "stored" | "live"


class ForecastService:
    def __init__(
        self,
        *,
        predictions: PredictionRepositoryPort,
        snapshots: Optional[SnapshotRepository] = None,
        model_repo: Optional[ModelRepository] = None,
        registry: Optional[FileModelRegistry] = None,
    ) -> None:
        self.predictions = predictions
        self.snapshots = snapshots
        self.model_repo = model_repo
        self.registry = registry

    def get(self, instrument: Instrument, horizon: Horizon) -> Optional[ForecastView]:
        stored = self.predictions.latest(instrument.id, horizon.value)
        if stored is not None:
            return self._from_stored(stored, horizon)
        if self.snapshots is None or self.model_repo is None or self.registry is None:
            return None
        return self._live(instrument, horizon)

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _from_stored(pred: Prediction, horizon: Horizon) -> ForecastView:
        quantiles = pred.quantiles or {}
        last_price = float(pred.last_price)
        predicted_price = float(pred.predicted_price)
        version = getattr(getattr(pred, "model_version", None), "version", None)
        return ForecastView(
            instrument_id=pred.instrument_id,
            horizon=horizon,
            as_of=pred.as_of_date,
            last_price=last_price,
            predicted_price=predicted_price,
            predicted_return=float(pred.predicted_return),
            expected_change_pct=(predicted_price / last_price - 1.0) * 100.0,
            quantiles_price={k: float(v) for k, v in quantiles.get("price", {}).items()},
            quantiles_return={k: float(v) for k, v in quantiles.get("return", {}).items()},
            model_version=version,
            is_synthetic=bool(pred.is_synthetic),
            source="stored",
        )

    def _live(self, instrument: Instrument, horizon: Horizon) -> Optional[ForecastView]:
        assert self.snapshots is not None and self.model_repo is not None
        assert self.registry is not None
        asset_class = instrument.asset_class.slug if instrument.asset_class else "pokemon"
        name = model_name_for(asset_class, horizon)
        version = self.model_repo.production_version(name, horizon.value)
        if version is None:
            return None
        model, card = self.registry.load(name)
        quantiles = [float(q) for q in card.get("quantiles", [0.1, 0.5, 0.9])]

        records = self.snapshots.history(instrument.id)
        frame = snapshots_to_frame(records)
        if frame.empty:
            return None
        release = instrument.release_date or frame.index[0].date()
        result = forecast_instrument(
            model, str(instrument.id), frame, release, horizon, quantiles=quantiles
        )
        if result is None:
            return None
        is_synthetic = any(r.is_synthetic for r in records)
        return ForecastView(
            instrument_id=instrument.id,
            horizon=horizon,
            as_of=result.as_of,
            last_price=result.last_price,
            predicted_price=result.predicted_price,
            predicted_return=result.predicted_return,
            expected_change_pct=result.expected_change_pct,
            quantiles_price={str(q): v for q, v in result.quantiles_price.items()},
            quantiles_return={str(q): v for q, v in result.quantiles_return.items()},
            model_version=version.version,
            is_synthetic=is_synthetic,
            source="live",
        )
