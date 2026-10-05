"""Price-history read service."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Optional

from pokequant.db.models import DailySnapshot
from pokequant.repositories.ports import SnapshotRepositoryPort


class PriceService:
    def __init__(self, snapshots: SnapshotRepositoryPort) -> None:
        self.snapshots = snapshots

    def history(
        self,
        instrument_id: uuid.UUID,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> Sequence[DailySnapshot]:
        return self.snapshots.history(instrument_id, start=start, end=end)

    def latest(self, instrument_id: uuid.UUID) -> Optional[DailySnapshot]:
        return self.snapshots.latest(instrument_id)
