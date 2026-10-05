"""Price-history endpoint."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from pokequant.api.deps import get_catalog_service, get_price_service
from pokequant.api.schemas import PriceHistoryResponse, PricePointSchema
from pokequant.core.errors import NotFoundError
from pokequant.services.catalog_service import CatalogService
from pokequant.services.price_service import PriceService

router = APIRouter()


@router.get("/instruments/{instrument_id}/prices", response_model=PriceHistoryResponse)
def get_prices(
    instrument_id: uuid.UUID,
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    catalog: CatalogService = Depends(get_catalog_service),
    prices: PriceService = Depends(get_price_service),
) -> PriceHistoryResponse:
    if catalog.get(instrument_id) is None:
        raise NotFoundError(f"Instrument {instrument_id} not found")
    history = prices.history(instrument_id, start=start, end=end)
    return PriceHistoryResponse(
        instrument_id=instrument_id,
        count=len(history),
        points=[PricePointSchema.from_snapshot(s) for s in history],
    )
