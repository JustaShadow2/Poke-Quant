"""Batch endpoints for bulk data fetches (performance optimization).

Instead of N individual requests for the scanner/dashboard, clients can fetch
multiple instruments' data in a single round-trip.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from pokequant.api.deps import get_session

router = APIRouter()


@router.get("/batch/instruments")
def batch_instruments(
    ids: str = Query(..., description="Comma-separated instrument IDs (max 20)"),
    horizon: str = Query(default="d90"),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Fetch forecast, score, and risk for multiple instruments in one call."""
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.ml_repo import PredictionRepository
    from pokequant.repositories.phase2_repo import (
        ExplanationRepository,
        RiskRepository,
        ScoreRepository,
    )

    id_list = [s.strip() for s in ids.split(",") if s.strip()][:20]

    cat_repo = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)
    pred_repo = PredictionRepository(session)
    score_repo = ScoreRepository(session)
    risk_repo = RiskRepository(session)
    explain_repo = ExplanationRepository(session)

    results: list[dict[str, Any]] = []
    for iid_str in id_list:
        try:
            iid = uuid.UUID(iid_str)
        except ValueError:
            continue

        inst = cat_repo.get(iid)
        if not inst:
            continue

        item: dict[str, Any] = {
            "instrument_id": str(inst.id),
            "symbol": inst.symbol,
            "name": inst.name,
        }

        # Price.
        record = snap_repo.latest(iid)
        item["price_usd"] = float(record.price_usd) if record else None

        # Forecast.
        pred = pred_repo.latest(iid, horizon)
        if pred:
            item["forecast"] = {
                "predicted_price": float(pred.predicted_price),
                "predicted_return": pred.predicted_return,
                "quantiles": pred.quantiles,
                "as_of_date": pred.as_of_date.isoformat(),
            }
        else:
            item["forecast"] = None

        # Score.
        score = score_repo.latest(iid, horizon)
        if score:
            item["score"] = {
                "score": score.score,
                "band": score.band,
                "components": score.components,
            }
        else:
            item["score"] = None

        # Risk.
        risk = risk_repo.latest(iid, horizon)
        if risk:
            item["risk"] = {
                "overall_score": risk.overall_score,
                "overall_level": risk.overall_level,
                "factors": risk.factors,
            }
        else:
            item["risk"] = None

        # Explanation (top drivers only, not full attributions).
        explain = explain_repo.latest(iid, horizon)
        if explain:
            item["explanation"] = {
                "narrative": explain.narrative,
                "top_positive": explain.top_positive,
                "top_negative": explain.top_negative,
            }
        else:
            item["explanation"] = None

        results.append(item)

    return {"horizon": horizon, "count": len(results), "instruments": results}
