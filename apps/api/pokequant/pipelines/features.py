"""Build point-in-time features from daily snapshots and store the latest row.

Training recomputes features from snapshots for reproducibility; this pipeline
persists the most recent feature vector per instrument as a serving/inspection
cache in `feature_values`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from pokequant.core.logging import get_logger
from pokequant.features.builder import FEATURE_SET, build_features
from pokequant.ml.dataset import snapshots_to_frame
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.features import FeatureRepository
from pokequant.repositories.market import SnapshotRepository

log = get_logger(__name__)


def _clean(value: Any) -> Any:
    return None if value is None or pd.isna(value) else float(value)


def build_and_store_features(session: Session, *, asset_class: str = "pokemon") -> dict[str, int]:
    catalog = CatalogRepository(session)
    snapshots = SnapshotRepository(session)
    features = FeatureRepository(session)

    instruments = catalog.all_active(asset_class)
    stored = 0
    for inst in instruments:
        history = snapshots.history(inst.id)
        frame = snapshots_to_frame(history)
        if frame.empty:
            continue
        release = inst.release_date or frame.index[0].date()
        computed = build_features(frame, release)
        if computed.empty:
            continue
        last = computed.iloc[-1]
        stored += features.bulk_upsert(
            [
                {
                    "instrument_id": inst.id,
                    "as_of_date": computed.index[-1].date(),
                    "feature_set": FEATURE_SET,
                    "values": {k: _clean(v) for k, v in last.items()},
                }
            ]
        )
    log.info("features_built", instruments=len(instruments), stored=stored)
    return {"instruments": len(instruments), "stored": stored}
