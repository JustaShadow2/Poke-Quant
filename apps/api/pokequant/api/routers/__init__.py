"""API routers aggregated under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from pokequant.api.routers import catalog, forecast, health, prices

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(catalog.router, prefix="/api/v1", tags=["catalog"])
api_router.include_router(prices.router, prefix="/api/v1", tags=["prices"])
api_router.include_router(forecast.router, prefix="/api/v1", tags=["forecast"])
