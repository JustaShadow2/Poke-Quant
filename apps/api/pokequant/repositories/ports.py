"""Repository Protocols consumed by the service layer (ports of the hexagon)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Optional, Protocol

from pokequant.db.models import DailySnapshot, Instrument, Prediction


class InstrumentRepositoryPort(Protocol):
    def list(
        self,
        *,
        asset_class: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> Sequence[Instrument]: ...

    def count(self, *, asset_class: Optional[str] = None, active_only: bool = True) -> int: ...

    def get(self, instrument_id: uuid.UUID) -> Optional[Instrument]: ...

    def get_by_symbol(self, symbol: str) -> Optional[Instrument]: ...


class SnapshotRepositoryPort(Protocol):
    def history(
        self,
        instrument_id: uuid.UUID,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> Sequence[DailySnapshot]: ...

    def latest(self, instrument_id: uuid.UUID) -> Optional[DailySnapshot]: ...


class PredictionRepositoryPort(Protocol):
    def latest(self, instrument_id: uuid.UUID, horizon: str) -> Optional[Prediction]: ...
