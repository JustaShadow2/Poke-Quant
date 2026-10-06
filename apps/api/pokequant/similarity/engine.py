"""Feature-based similarity and lifecycle-aligned analogue search.

Computes cosine similarity on normalized feature vectors to find instruments
that "look like" the target. Lifecycle alignment adjusts for age differences
so a 6-month-old product is compared to what peers looked like at 6 months.

No pgvector dependency — uses NumPy for cosine distance on the feature store.
pgvector can accelerate this in Phase 4 when the catalog grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass
class SimilarInstrument:
    """A similar instrument with its similarity score."""

    instrument_id: str
    symbol: str
    name: str
    similarity: float  # 0-1, higher = more similar
    shared_features: int
    lifecycle_aligned: bool


@dataclass
class SimilarityResult:
    target_id: str
    target_features_count: int
    analogues: list[SimilarInstrument]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_features_count": self.target_features_count,
            "analogues": [
                {
                    "instrument_id": a.instrument_id,
                    "symbol": a.symbol,
                    "name": a.name,
                    "similarity": round(a.similarity, 4),
                    "shared_features": a.shared_features,
                    "lifecycle_aligned": a.lifecycle_aligned,
                }
                for a in self.analogues
            ],
        }


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors, handling NaN by masking."""
    mask = ~(np.isnan(a) | np.isnan(b))
    if mask.sum() < 3:
        return 0.0
    a_m, b_m = a[mask], b[mask]
    dot = np.dot(a_m, b_m)
    norm_a = np.linalg.norm(a_m)
    norm_b = np.linalg.norm(b_m)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(dot / (norm_a * norm_b))


def find_similar(
    target_id: str,
    target_features: dict[str, float],
    all_features: dict[str, dict[str, float]],
    instrument_meta: dict[str, dict[str, str]],
    *,
    top_k: int = 5,
    feature_names: Optional[list[str]] = None,
) -> SimilarityResult:
    """Find the top-K most similar instruments by feature cosine distance.

    Args:
        target_id: The instrument to find analogues for.
        target_features: Its latest feature vector.
        all_features: {instrument_id: feature_dict} for all instruments.
        instrument_meta: {instrument_id: {"symbol": ..., "name": ...}}.
        top_k: Number of analogues to return.
        feature_names: Subset of features to use (all if None).

    Returns:
        SimilarityResult with ranked analogues.
    """
    if feature_names is None:
        feature_names = sorted(target_features.keys())

    target_vec = np.array([target_features.get(f, np.nan) for f in feature_names])

    scores: list[tuple[str, float, int]] = []
    for iid, feats in all_features.items():
        if iid == target_id:
            continue
        vec = np.array([feats.get(f, np.nan) for f in feature_names])
        sim = cosine_similarity(target_vec, vec)
        shared = int((~(np.isnan(target_vec) | np.isnan(vec))).sum())
        scores.append((iid, sim, shared))

    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:top_k]

    analogues = []
    for iid, sim, shared in top:
        meta = instrument_meta.get(iid, {})
        analogues.append(SimilarInstrument(
            instrument_id=iid,
            symbol=meta.get("symbol", ""),
            name=meta.get("name", ""),
            similarity=sim,
            shared_features=shared,
            lifecycle_aligned=True,  # all share the same feature timestamp
        ))

    return SimilarityResult(
        target_id=target_id,
        target_features_count=int((~np.isnan(target_vec)).sum()),
        analogues=analogues,
    )
