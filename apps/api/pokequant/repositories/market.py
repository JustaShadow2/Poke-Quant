"""Market-data repositories: raw observations, daily snapshots, macro series."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pokequant.db.models import DailySnapshot, MacroSeriesValue, PriceObservation


class PriceObservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bulk_upsert(self, rows: Iterable[dict[str, Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        stmt = pg_insert(PriceObservation).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_price_observations_dedupe",
            set_={
                "price_usd": stmt.excluded.price_usd,
                "volume": stmt.excluded.volume,
                "source_url": stmt.excluded.source_url,
                "provider_run_id": stmt.excluded.provider_run_id,
            },
        )
        self.session.execute(stmt)
        return len(rows)


class SnapshotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bulk_upsert(self, rows: Iterable[dict[str, Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        stmt = pg_insert(DailySnapshot).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailySnapshot.instrument_id, DailySnapshot.snapshot_date],
            set_={
                "price_usd": stmt.excluded.price_usd,
                "price_source": stmt.excluded.price_source,
                "price_kind": stmt.excluded.price_kind,
                "volume": stmt.excluded.volume,
                "active_listings": stmt.excluded.active_listings,
                "attention_index": stmt.excluded.attention_index,
                "is_synthetic": stmt.excluded.is_synthetic,
            },
        )
        self.session.execute(stmt)
        return len(rows)

    def history(
        self,
        instrument_id: uuid.UUID,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> Sequence[DailySnapshot]:
        stmt = select(DailySnapshot).where(DailySnapshot.instrument_id == instrument_id)
        if start is not None:
            stmt = stmt.where(DailySnapshot.snapshot_date >= start)
        if end is not None:
            stmt = stmt.where(DailySnapshot.snapshot_date <= end)
        stmt = stmt.order_by(DailySnapshot.snapshot_date)
        return self.session.execute(stmt).scalars().all()

    def latest(self, instrument_id: uuid.UUID) -> Optional[DailySnapshot]:
        stmt = (
            select(DailySnapshot)
            .where(DailySnapshot.instrument_id == instrument_id)
            .order_by(DailySnapshot.snapshot_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def has_any(self, instrument_id: uuid.UUID) -> bool:
        stmt = (
            select(DailySnapshot.snapshot_date)
            .where(DailySnapshot.instrument_id == instrument_id)
            .limit(1)
        )
        return self.session.execute(stmt).first() is not None


class MacroRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bulk_upsert(self, rows: Iterable[dict[str, Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        stmt = pg_insert(MacroSeriesValue).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[MacroSeriesValue.series_id, MacroSeriesValue.observed_at],
            set_={"value": stmt.excluded.value},
        )
        self.session.execute(stmt)
        return len(rows)
