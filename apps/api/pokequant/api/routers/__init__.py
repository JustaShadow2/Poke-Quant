"""API routers aggregated under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from pokequant.api.routers import batch, cards, catalog, forecast, health, phase2, phase3, prices

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(catalog.router, prefix="/api/v1", tags=["catalog"])
api_router.include_router(prices.router, prefix="/api/v1", tags=["prices"])
api_router.include_router(forecast.router, prefix="/api/v1", tags=["forecast"])
api_router.include_router(cards.router, prefix="/api/v1", tags=["cards"])
api_router.include_router(phase2.router, prefix="/api/v1", tags=["explainability", "scoring", "risk"])
api_router.include_router(phase3.router, prefix="/api/v1", tags=["portfolio", "watchlist", "alerts", "scanner", "montecarlo", "similarity", "assistant", "dashboard"])
api_router.include_router(batch.router, prefix="/api/v1", tags=["batch"])
