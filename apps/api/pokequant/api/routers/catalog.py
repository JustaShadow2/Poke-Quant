"""Catalog endpoints: list and fetch instruments."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query

from pokequant.api.deps import get_catalog_service
from pokequant.api.schemas import InstrumentListResponse, InstrumentSummary
from pokequant.core.errors import NotFoundError
from pokequant.services.catalog_service import CatalogService

router = APIRouter()


@router.get("/instruments", response_model=InstrumentListResponse)
def list_instruments(
    asset_class: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: CatalogService = Depends(get_catalog_service),
) -> InstrumentListResponse:
    items, total = service.list_instruments(asset_class=asset_class, limit=limit, offset=offset)
    return InstrumentListResponse(
        items=[InstrumentSummary.from_instrument(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/instruments/{instrument_id}", response_model=InstrumentSummary)
def get_instrument(
    instrument_id: uuid.UUID,
    service: CatalogService = Depends(get_catalog_service),
) -> InstrumentSummary:
    inst = service.get(instrument_id)
    if inst is None:
        raise NotFoundError(f"Instrument {instrument_id} not found")
    return InstrumentSummary.from_instrument(inst)
