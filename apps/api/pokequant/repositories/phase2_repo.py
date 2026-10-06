"""Repositories for Phase 2 tables: explanations, scores, risk, calibrations."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pokequant.db.models import (
    ConformalCalibration,
    InvestmentScoreRecord,
    PredictionExplanation,
    RiskAssessmentRecord,
)


class ExplanationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        prediction_id: uuid.UUID,
        instrument_id: uuid.UUID,
        horizon: str,
        as_of_date: date,
        base_value: float,
        attributions: dict[str, Any],
        top_positive: list[dict[str, Any]],
        top_negative: list[dict[str, Any]],
        narrative: Optional[str] = None,
        model_version_id: Optional[uuid.UUID] = None,
    ) -> None:
        stmt = pg_insert(PredictionExplanation).values(
            prediction_id=prediction_id,
            instrument_id=instrument_id,
            horizon=horizon,
            as_of_date=as_of_date,
            base_value=base_value,
            attributions=attributions,
            top_positive=top_positive,
            top_negative=top_negative,
            narrative=narrative,
            model_version_id=model_version_id,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_explanation_prediction",
            set_={
                "base_value": stmt.excluded.base_value,
                "attributions": stmt.excluded.attributions,
                "top_positive": stmt.excluded.top_positive,
                "top_negative": stmt.excluded.top_negative,
                "narrative": stmt.excluded.narrative,
                "model_version_id": stmt.excluded.model_version_id,
            },
        )
        self.session.execute(stmt)

    def latest(self, instrument_id: uuid.UUID, horizon: str) -> Optional[PredictionExplanation]:
        stmt = (
            select(PredictionExplanation)
            .where(
                PredictionExplanation.instrument_id == instrument_id,
                PredictionExplanation.horizon == horizon,
            )
            .order_by(PredictionExplanation.as_of_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()


class ScoreRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        instrument_id: uuid.UUID,
        as_of_date: date,
        horizon: str,
        profile: str,
        score: float,
        band: str,
        raw_score: float,
        components: list[dict[str, Any]],
        reprint_penalty: float = 0.0,
        risk_penalty: float = 0.0,
        data_coverage: float = 1.0,
        is_sufficient: bool = True,
        model_version_id: Optional[uuid.UUID] = None,
    ) -> None:
        stmt = pg_insert(InvestmentScoreRecord).values(
            instrument_id=instrument_id,
            as_of_date=as_of_date,
            horizon=horizon,
            profile=profile,
            score=score,
            band=band,
            raw_score=raw_score,
            components=components,
            reprint_penalty=reprint_penalty,
            risk_penalty=risk_penalty,
            data_coverage=data_coverage,
            is_sufficient=is_sufficient,
            model_version_id=model_version_id,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_score_instrument_date_horizon",
            set_={
                "score": stmt.excluded.score,
                "band": stmt.excluded.band,
                "raw_score": stmt.excluded.raw_score,
                "components": stmt.excluded.components,
                "reprint_penalty": stmt.excluded.reprint_penalty,
                "risk_penalty": stmt.excluded.risk_penalty,
                "data_coverage": stmt.excluded.data_coverage,
                "is_sufficient": stmt.excluded.is_sufficient,
                "model_version_id": stmt.excluded.model_version_id,
            },
        )
        self.session.execute(stmt)

    def latest(self, instrument_id: uuid.UUID, horizon: str) -> Optional[InvestmentScoreRecord]:
        stmt = (
            select(InvestmentScoreRecord)
            .where(
                InvestmentScoreRecord.instrument_id == instrument_id,
                InvestmentScoreRecord.horizon == horizon,
            )
            .order_by(InvestmentScoreRecord.as_of_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()


class RiskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        instrument_id: uuid.UUID,
        as_of_date: date,
        horizon: str,
        overall_score: float,
        overall_level: str,
        factors: list[dict[str, Any]],
        narrative: Optional[str] = None,
    ) -> None:
        stmt = pg_insert(RiskAssessmentRecord).values(
            instrument_id=instrument_id,
            as_of_date=as_of_date,
            horizon=horizon,
            overall_score=overall_score,
            overall_level=overall_level,
            factors=factors,
            narrative=narrative,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_risk_instrument_date_horizon",
            set_={
                "overall_score": stmt.excluded.overall_score,
                "overall_level": stmt.excluded.overall_level,
                "factors": stmt.excluded.factors,
                "narrative": stmt.excluded.narrative,
            },
        )
        self.session.execute(stmt)

    def latest(self, instrument_id: uuid.UUID, horizon: str) -> Optional[RiskAssessmentRecord]:
        stmt = (
            select(RiskAssessmentRecord)
            .where(
                RiskAssessmentRecord.instrument_id == instrument_id,
                RiskAssessmentRecord.horizon == horizon,
            )
            .order_by(RiskAssessmentRecord.as_of_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()


class CalibrationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        model_version_id: uuid.UUID,
        nominal_coverage: float,
        lo_quantile: float,
        hi_quantile: float,
        adjustment: float,
        coverage_before: float,
        coverage_after: float,
        n_calibration: int,
    ) -> None:
        stmt = pg_insert(ConformalCalibration).values(
            model_version_id=model_version_id,
            nominal_coverage=nominal_coverage,
            lo_quantile=lo_quantile,
            hi_quantile=hi_quantile,
            adjustment=adjustment,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            n_calibration=n_calibration,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_conformal_model_quantiles",
            set_={
                "adjustment": stmt.excluded.adjustment,
                "coverage_before": stmt.excluded.coverage_before,
                "coverage_after": stmt.excluded.coverage_after,
                "n_calibration": stmt.excluded.n_calibration,
            },
        )
        self.session.execute(stmt)

    def latest_for_model(self, model_version_id: uuid.UUID) -> Optional[ConformalCalibration]:
        stmt = (
            select(ConformalCalibration)
            .where(ConformalCalibration.model_version_id == model_version_id)
            .order_by(ConformalCalibration.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()
