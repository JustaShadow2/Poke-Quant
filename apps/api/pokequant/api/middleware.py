"""Application middleware: logging, compression, rate limiting, security headers."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from pokequant.core.logging import get_logger

logger = get_logger("http")


# ---------------------------------------------------------------------------
# Structured request logging
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, duration, and request ID."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Attach request_id for downstream correlation.
        request.state.request_id = request_id

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
            request_id=request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory, per-IP token bucket)
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Simple per-key token bucket for rate limiting."""

    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_time)

    def allow(self, key: str) -> bool:
        now = time.time()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        elapsed = now - last
        tokens = min(self.capacity, tokens + elapsed * self.rate)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True
        self._buckets[key] = (tokens, now)
        return False


# 60 requests per minute per IP (generous for a portfolio project).
_limiter = _TokenBucket(rate=1.0, capacity=60.0)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting. Returns 429 if exceeded."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks.
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if not _limiter.allow(client_ip):
            return Response(
                content='{"detail":"Rate limit exceeded. Try again shortly."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "5"},
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


# ---------------------------------------------------------------------------
# Install all middleware on app
# ---------------------------------------------------------------------------


def install_middleware(app: FastAPI) -> None:
    """Add all middleware to the FastAPI app (order matters: last added = first executed)."""
    # GZip compression for responses > 500 bytes.
    app.add_middleware(GZipMiddleware, minimum_size=500)
    # Security headers.
    app.add_middleware(SecurityHeadersMiddleware)
    # Rate limiting.
    app.add_middleware(RateLimitMiddleware)
    # Request logging (outermost = logs first).
    app.add_middleware(RequestLoggingMiddleware)
