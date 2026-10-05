"""Normalized value objects exchanged between layers.

Providers emit these; the ingestion service resolves them to internal instrument
ids and persists them. Keeping them framework-free (pydantic v2) makes every
provider and transform unit-testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from pokequant.domain.enums import Condition, PriceKind

T = TypeVar("T")


class InstrumentQuery(BaseModel):
    """Everything a provider needs to locate data for one instrument.

    `identifiers` holds source-specific keys, e.g.
    ``{"ebay_query": "Prismatic Evolutions ETB", "pricecharting_id": "...",
       "ptcg_set_id": "sv8pt5"}``.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    symbol: str
    name: str
    identifiers: dict[str, str] = Field(default_factory=dict)


class PricePoint(BaseModel):
    """A single normalized price observation (already converted to USD)."""

    model_config = ConfigDict(frozen=True)

    observed_at: datetime
    price_usd: float = Field(gt=0)
    kind: PriceKind
    condition: Condition = Condition.SEALED
    currency: str = "USD"
    volume: Optional[int] = None
    source_url: Optional[str] = None


class SupplyPoint(BaseModel):
    """Point-in-time supply/liquidity signal (e.g. active listing count)."""

    model_config = ConfigDict(frozen=True)

    observed_at: datetime
    active_listings: Optional[int] = None
    sales_volume: Optional[int] = None


class MacroPoint(BaseModel):
    """A single observation of a macroeconomic series."""

    model_config = ConfigDict(frozen=True)

    series_id: str
    observed_at: datetime
    value: float


@dataclass(frozen=True)
class ProviderInfo:
    """Static metadata describing a provider adapter."""

    slug: str
    name: str
    # Reliability tier from docs/02-data-sources.md (1 = best, 4 = weak/synthetic).
    tier: int
    is_synthetic: bool = False


@dataclass
class ProviderResult(Generic[T]):
    """Container for provider output plus lightweight run telemetry."""

    items: list[T] = field(default_factory=list)
    request_count: int = 0
    notes: list[str] = field(default_factory=list)
    raw_sample: Optional[dict[str, Any]] = None

    def extend(self, other: ProviderResult[T]) -> None:
        self.items.extend(other.items)
        self.request_count += other.request_count
        self.notes.extend(other.notes)
        if self.raw_sample is None:
            self.raw_sample = other.raw_sample
