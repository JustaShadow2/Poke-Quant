"""Health / readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pokequant import __version__
from pokequant.api.schemas import HealthResponse
from pokequant.core.config import Settings, get_settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, env=settings.env)
