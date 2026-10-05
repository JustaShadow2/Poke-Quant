"""Catalog read service."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Optional

from pokequant.db.models import Instrument
from pokequant.repositories.ports import InstrumentRepositoryPort


class CatalogService:
    def __init__(self, instruments: InstrumentRepositoryPort) -> None:
        self.instruments = instruments

    def list_instruments(
        self, *, asset_class: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[Instrument], int]:
        items = self.instruments.list(asset_class=asset_class, limit=limit, offset=offset)
        total = self.instruments.count(asset_class=asset_class)
        return items, total

    def get(self, instrument_id: uuid.UUID) -> Optional[Instrument]:
        return self.instruments.get(instrument_id)

    def get_by_symbol(self, symbol: str) -> Optional[Instrument]:
        return self.instruments.get_by_symbol(symbol)
