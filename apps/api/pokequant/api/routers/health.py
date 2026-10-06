"""Health / readiness endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

from pokequant import __version__
from pokequant.api.schemas import HealthResponse
from pokequant.core.config import Settings, get_settings

router = APIRouter()

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, env=settings.env)


@router.get("/health/detailed")
def health_detailed(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Enriched health check with uptime, DB connectivity, Redis status."""
    uptime_seconds = int(time.time() - _start_time)

    # DB check.
    db_ok = False
    try:
        from pokequant.db.session import get_session
        from sqlalchemy import text
        session = next(get_session())
        session.execute(text("SELECT 1"))
        db_ok = True
        session.close()
    except Exception:
        pass

    # Redis check.
    redis_ok = False
    try:
        from pokequant.api.cache import _get_redis
        r = _get_redis()
        if r:
            r.ping()
            redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "env": settings.env,
        "uptime_seconds": uptime_seconds,
        "checks": {
            "database": "connected" if db_ok else "unreachable",
            "redis": "connected" if redis_ok else "unavailable",
            "artifact_dir": str(settings.artifact_dir),
        },
        "features": {
            "groq_configured": settings.groq_api_key is not None,
            "ebay_configured": settings.ebay_client_id is not None,
            "fred_configured": settings.fred_api_key is not None,
        },
    }
