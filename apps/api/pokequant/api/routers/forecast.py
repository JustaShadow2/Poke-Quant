"""Forecast endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from pokequant.api.deps import get_catalog_service, get_forecast_service
from pokequant.api.schemas import ForecastResponse
from pokequant.core.errors import NotFoundError
from pokequant.domain.enums import Horizon
from pokequant.services.catalog_service import CatalogService
from pokequant.services.forecast_service import ForecastService

router = APIRouter()


@router.get("/instruments/{instrument_id}/forecast", response_model=ForecastResponse)
def get_forecast(
    instrument_id: uuid.UUID,
    horizon: Horizon = Query(default=Horizon.D90),
    catalog: CatalogService = Depends(get_catalog_service),
    forecasts: ForecastService = Depends(get_forecast_service),
) -> ForecastResponse:
    inst = catalog.get(instrument_id)
    if inst is None:
        raise NotFoundError(f"Instrument {instrument_id} not found")
    view = forecasts.get(inst, horizon)
    if view is None:
        raise NotFoundError(
            f"No forecast available for instrument {instrument_id} at horizon {horizon.value}"
        )
    return ForecastResponse.from_view(view)
