"""Batch forecasting: load the production model and persist predictions."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pokequant.core.errors import NotFoundError
from pokequant.core.logging import get_logger
from pokequant.domain.enums import Horizon
from pokequant.ml.dataset import snapshots_to_frame
from pokequant.ml.forecast import forecast_instrument
from pokequant.ml.registry import FileModelRegistry
from pokequant.ml.train import model_name_for
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import SnapshotRepository
from pokequant.repositories.ml_repo import ModelRepository, PredictionRepository

log = get_logger(__name__)


def _money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def run_forecasts(
    session: Session,
    registry: FileModelRegistry,
    *,
    horizon: Horizon,
    asset_class: str = "pokemon",
) -> dict[str, object]:
    catalog = CatalogRepository(session)
    snapshots = SnapshotRepository(session)
    model_repo = ModelRepository(session)
    predictions = PredictionRepository(session)

    name = model_name_for(asset_class, horizon)
    version = model_repo.production_version(name, horizon.value)
    if version is None:
        raise NotFoundError(f"No production model for {name!r}; run training first")

    model, card = registry.load(name)
    quantiles = [float(q) for q in card.get("quantiles", [0.1, 0.5, 0.9])]

    written = 0
    for inst in catalog.all_active(asset_class):
        records = snapshots.history(inst.id)
        if not records:
            continue
        frame = snapshots_to_frame(records)
        release = inst.release_date or frame.index[0].date()
        result = forecast_instrument(
            model, str(inst.id), frame, release, horizon, quantiles=quantiles
        )
        if result is None:
            continue
        is_synthetic = any(r.is_synthetic for r in records)
        predictions.upsert(
            instrument_id=inst.id,
            model_version_id=version.id,
            horizon=horizon.value,
            as_of_date=result.as_of,
            last_price=_money(result.last_price),
            predicted_price=_money(result.predicted_price),
            predicted_return=result.predicted_return,
            quantiles={
                "return": {str(q): v for q, v in result.quantiles_return.items()},
                "price": {str(q): v for q, v in result.quantiles_price.items()},
            },
            is_synthetic=is_synthetic,
        )
        written += 1

    log.info("forecasts_written", model=name, version=version.version, count=written)
    return {"forecasts": written, "model_version": version.version}
