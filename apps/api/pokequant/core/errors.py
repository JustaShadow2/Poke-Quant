"""Framework-agnostic application error hierarchy.

Kept free of any web-framework imports so the domain/service layers can raise
these without depending on FastAPI. The HTTP mapping lives in `api/errors.py`.
"""

from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
    """Base class for expected, handled application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ConfigurationError(AppError):
    status_code = 500
    code = "configuration_error"


class ProviderError(AppError):
    """A downstream data provider failed."""

    status_code = 502
    code = "provider_error"


class RateLimitedError(ProviderError):
    status_code = 429
    code = "rate_limited"
