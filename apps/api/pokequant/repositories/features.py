"""Feature-store repository."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pokequant.db.models import FeatureValue


class FeatureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bulk_upsert(self, rows: Iterable[dict[str, Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        stmt = pg_insert(FeatureValue).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                FeatureValue.instrument_id,
                FeatureValue.as_of_date,
                FeatureValue.feature_set,
            ],
            set_={"values": stmt.excluded.values},
        )
        self.session.execute(stmt)
        return len(rows)
