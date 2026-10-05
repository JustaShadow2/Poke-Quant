"""Enumerations shared across the platform.

All are string-valued for stable serialization and human-readable storage
(we persist them via SQLAlchemy `Enum(..., native_enum=False)` -> VARCHAR+CHECK).
"""

from __future__ import annotations

from enum import Enum


class PriceKind(str, Enum):
    """What a price observation represents."""

    SALE = "sale"  # a realized transaction (e.g. eBay sold)
    LISTING = "listing"  # an ask / active listing price
    MARKET = "market"  # a provider's consolidated market/mid price
    INDEX = "index"  # a synthetic or computed index level


class Condition(str, Enum):
    SEALED = "sealed"
    NEW = "new"
    USED = "used"
    GRADED = "graded"
    UNKNOWN = "unknown"


class Horizon(str, Enum):
    """Forecast horizons (calendar days ahead)."""

    D30 = "d30"
    D90 = "d90"
    D180 = "d180"
    D365 = "d365"

    @property
    def days(self) -> int:
        return {"d30": 30, "d90": 90, "d180": 180, "d365": 365}[self.value]

    @classmethod
    def from_days(cls, days: int) -> Horizon:
        for h in cls:
            if h.days == days:
                return h
        raise ValueError(f"No horizon for {days} days")


class ModelKind(str, Enum):
    NAIVE = "naive"
    SEASONAL_NAIVE = "seasonal_naive"
    GBM = "gbm"


class ModelStage(str, Enum):
    NONE = "none"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
