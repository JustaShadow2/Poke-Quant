"""Redis caching layer for expensive computations.

Caches forecasts, scores, and risk assessments by (instrument_id, horizon).
Invalidates when new data arrives (called after ingest/forecast/phase2 pipelines).

Degrades gracefully: if Redis is unavailable, all operations silently no-op.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_client: Any = None
_initialized: bool = False

DEFAULT_TTL = 3600  # 1 hour; pipelines invalidate on update anyway.


def _get_redis() -> Any:
    """Lazy-initialize Redis connection. Returns None if unavailable."""
    global _redis_client, _initialized
    if _initialized:
        return _redis_client
    _initialized = True

    from pokequant.core.config import get_settings
    settings = get_settings()
    if not settings.redis_url:
        logger.info("cache_disabled", reason="no REDIS_URL configured")
        return None

    try:
        import redis
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("cache_connected", url=settings.redis_url)
    except Exception as exc:
        logger.warning("cache_unavailable", error=str(exc))
        _redis_client = None
    return _redis_client


def _key(prefix: str, instrument_id: str, horizon: str) -> str:
    return f"pq:{prefix}:{instrument_id}:{horizon}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_cached(prefix: str, instrument_id: str, horizon: str) -> Optional[dict[str, Any]]:
    """Retrieve a cached value. Returns None on miss or if Redis is down."""
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(_key(prefix, instrument_id, horizon))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def set_cached(
    prefix: str, instrument_id: str, horizon: str, data: dict[str, Any], ttl: int = DEFAULT_TTL
) -> None:
    """Store a value in cache."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(_key(prefix, instrument_id, horizon), ttl, json.dumps(data, default=str))
    except Exception:
        pass


def invalidate(prefix: str, instrument_id: str, horizon: str) -> None:
    """Delete a specific cache entry."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(_key(prefix, instrument_id, horizon))
    except Exception:
        pass


def invalidate_instrument(instrument_id: str) -> None:
    """Invalidate all cached data for an instrument (all prefixes, all horizons)."""
    r = _get_redis()
    if r is None:
        return
    try:
        pattern = f"pq:*:{instrument_id}:*"
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def invalidate_all() -> None:
    """Flush all PokéQuant cache entries (after a full pipeline run)."""
    r = _get_redis()
    if r is None:
        return
    try:
        pattern = "pq:*"
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass
