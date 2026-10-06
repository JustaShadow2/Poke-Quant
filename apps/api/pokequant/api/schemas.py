"""Pydantic response models (the API contract).

Explicit constructors (`from_*`) map ORM rows -> DTOs so the wire format is
decoupled from the database schema.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel

from pokequant.db.models import DailySnapshot, Instrument
from pokequant.domain.enums import Horizon
from pokequant.services.forecast_service import ForecastView

SYNTHETIC_DISCLAIMER = (
    "This forecast is derived (partly or wholly) from calibrated synthetic data and "
    "is for demonstration only - not investment advice."
)


class InstrumentSummary(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    asset_class: str
    category: Optional[str] = None
    release_date: Optional[date] = None
    msrp_usd: Optional[float] = None
    currency: str = "USD"
    is_active: bool = True

    @classmethod
    def from_instrument(cls, inst: Instrument) -> InstrumentSummary:
        return cls(
            id=inst.id,
            symbol=inst.symbol,
            name=inst.name,
            asset_class=inst.asset_class.slug if inst.asset_class else "",
            category=inst.category.name if inst.category else None,
            release_date=inst.release_date,
            msrp_usd=float(inst.msrp_usd) if inst.msrp_usd is not None else None,
            currency=inst.currency,
            is_active=inst.is_active,
        )


class InstrumentListResponse(BaseModel):
    items: list[InstrumentSummary]
    total: int
    limit: int
    offset: int


class PricePointSchema(BaseModel):
    date: date
    price_usd: float
    source: str
    volume: Optional[int] = None
    active_listings: Optional[int] = None
    attention_index: Optional[float] = None
    is_synthetic: bool = False

    @classmethod
    def from_snapshot(cls, snap: DailySnapshot) -> PricePointSchema:
        return cls(
            date=snap.snapshot_date,
            price_usd=float(snap.price_usd),
            source=snap.price_source,
            volume=snap.volume,
            active_listings=snap.active_listings,
            attention_index=snap.attention_index,
            is_synthetic=snap.is_synthetic,
        )


class PriceHistoryResponse(BaseModel):
    instrument_id: uuid.UUID
    count: int
    points: list[PricePointSchema]


class ForecastResponse(BaseModel):
    instrument_id: uuid.UUID
    horizon: Horizon
    as_of: date
    last_price: float
    predicted_price: float
    predicted_return: float
    expected_change_pct: float
    quantiles_price: dict[str, float]
    quantiles_return: dict[str, float]
    model_version: Optional[str]
    is_synthetic: bool
    source: str
    disclaimer: Optional[str] = None

    @classmethod
    def from_view(cls, view: ForecastView) -> ForecastResponse:
        return cls(
            instrument_id=view.instrument_id,
            horizon=view.horizon,
            as_of=view.as_of,
            last_price=round(view.last_price, 2),
            predicted_price=round(view.predicted_price, 2),
            predicted_return=view.predicted_return,
            expected_change_pct=round(view.expected_change_pct, 2),
            quantiles_price={k: round(v, 2) for k, v in view.quantiles_price.items()},
            quantiles_return=view.quantiles_return,
            model_version=view.model_version,
            is_synthetic=view.is_synthetic,
            source=view.source,
            disclaimer=SYNTHETIC_DISCLAIMER if view.is_synthetic else None,
        )


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str


class CardSummary(BaseModel):
    id: str
    name: str
    set_name: str
    set_id: str
    number: str
    rarity: Optional[str] = None
    artist: Optional[str] = None
    image_small: Optional[str] = None
    image_large: Optional[str] = None
    tcgplayer_url: Optional[str] = None
    raw_usd: Optional[float] = None
    raw_finish: Optional[str] = None
    raw_low: Optional[float] = None
    raw_mid: Optional[float] = None
    raw_high: Optional[float] = None
    prices_updated_at: Optional[str] = None
    raw_source: Optional[str] = None
    graded_source: Optional[str] = None


class CardSearchResponse(BaseModel):
    query: str
    count: int
    items: list[CardSummary]


class GradedPrices(BaseModel):
    raw_usd: float
    psa9_usd: float
    psa10_usd: float
    psa8_usd: float
    raw_source: str
    graded_source: str
    graded_note: str


class GradeROISchema(BaseModel):
    raw_usd: float
    psa8_usd: float
    psa9_usd: float
    psa10_usd: float
    grading_fee_usd: float
    shipping_usd: float
    all_in_cost_usd: float
    p10: float
    p9: float
    p8: float
    expected_grade_proceeds: float
    expected_net_vs_raw: float
    breakeven_p10: Optional[float] = None
    verdict: str
    rationale: str
    prices_are_estimated: bool
    probs_source: str


class CardValuationResponse(BaseModel):
    card: CardSummary
    prices: GradedPrices
    roi: GradeROISchema


class VisionSubgrade(BaseModel):
    name: str
    score: float
    notes: str


class VisionGradeResponse(BaseModel):
    predicted_grade: float
    centering: VisionSubgrade
    corners: VisionSubgrade
    edges: VisionSubgrade
    surface: VisionSubgrade
    method: str
    disclaimer: str


class VisionROIResponse(CardValuationResponse):
    vision: VisionGradeResponse
