"""Phase 2 API endpoints: explanations, investment scores, risk assessments."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from pokequant.api.deps import get_session
from pokequant.domain.enums import Horizon
from pokequant.repositories.phase2_repo import (
    ExplanationRepository,
    RiskRepository,
    ScoreRepository,
)

router = APIRouter()


@router.get("/instruments/{instrument_id}/explain")
def get_explanation(
    instrument_id: uuid.UUID,
    horizon: str = Query(default="d90"),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Get the SHAP-based explanation for the latest prediction."""
    repo = ExplanationRepository(session)
    record = repo.latest(instrument_id, horizon)
    if record is None:
        return {
            "instrument_id": str(instrument_id),
            "horizon": horizon,
            "available": False,
            "message": "No explanation available. Run the Phase 2 pipeline first.",
        }
    return {
        "instrument_id": str(instrument_id),
        "horizon": horizon,
        "available": True,
        "as_of_date": record.as_of_date.isoformat(),
        "base_value": record.base_value,
        "top_positive": record.top_positive,
        "top_negative": record.top_negative,
        "narrative": record.narrative,
        "attributions": record.attributions,
        "model_version_id": str(record.model_version_id) if record.model_version_id else None,
    }


@router.get("/instruments/{instrument_id}/score")
def get_score(
    instrument_id: uuid.UUID,
    horizon: str = Query(default="d90"),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Get the latest Investment Score breakdown."""
    repo = ScoreRepository(session)
    record = repo.latest(instrument_id, horizon)
    if record is None:
        return {
            "instrument_id": str(instrument_id),
            "horizon": horizon,
            "available": False,
            "message": "No score available. Run the Phase 2 pipeline first.",
        }
    return {
        "instrument_id": str(instrument_id),
        "horizon": horizon,
        "available": True,
        "as_of_date": record.as_of_date.isoformat(),
        "score": record.score,
        "band": record.band,
        "raw_score": record.raw_score,
        "profile": record.profile,
        "components": record.components,
        "reprint_penalty": record.reprint_penalty,
        "risk_penalty": record.risk_penalty,
        "data_coverage": record.data_coverage,
        "is_sufficient": record.is_sufficient,
    }


@router.get("/instruments/{instrument_id}/risk")
def get_risk(
    instrument_id: uuid.UUID,
    horizon: str = Query(default="d90"),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Get the latest Risk Assessment."""
    repo = RiskRepository(session)
    record = repo.latest(instrument_id, horizon)
    if record is None:
        return {
            "instrument_id": str(instrument_id),
            "horizon": horizon,
            "available": False,
            "message": "No risk assessment available. Run the Phase 2 pipeline first.",
        }
    return {
        "instrument_id": str(instrument_id),
        "horizon": horizon,
        "available": True,
        "as_of_date": record.as_of_date.isoformat(),
        "overall_score": record.overall_score,
        "overall_level": record.overall_level,
        "factors": record.factors,
        "narrative": record.narrative,
    }
