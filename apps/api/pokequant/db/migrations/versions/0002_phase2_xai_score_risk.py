"""Phase 2: explainability, investment scores, risk assessments, conformal calibration

Adds tables for:
- prediction_explanations: SHAP attributions per prediction
- investment_scores: composite 0-100 score with component breakdown
- risk_assessments: probability x severity risk factors
- conformal_calibrations: stored CQR calibration state per model

Revision ID: 0002_phase2_xai_score_risk
Revises: 0001_initial
Create Date: 2026-08-14
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_phase2"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These tables may already exist if 0001_initial ran after the Phase 2 models
    # were added to db/models.py (since 0001 uses Base.metadata.create_all).
    # Use raw DDL with IF NOT EXISTS to be idempotent.
    bind = op.get_bind()

    # Only create tables that don't already exist.
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(bind)
    existing = set(inspector.get_table_names())

    if "prediction_explanations" not in existing:
        op.create_table(
            "prediction_explanations",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("prediction_id", sa.Uuid(), sa.ForeignKey("predictions.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("horizon", sa.String(8), nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("base_value", sa.Float(), nullable=False),
            sa.Column("attributions", JSONB(), nullable=False),
            sa.Column("top_positive", JSONB(), server_default="[]"),
            sa.Column("top_negative", JSONB(), server_default="[]"),
            sa.Column("narrative", sa.Text()),
            sa.Column("model_version_id", sa.Uuid(),
                      sa.ForeignKey("model_versions.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("prediction_id", name="uq_explanation_prediction"),
        )

    if "investment_scores" not in existing:
        op.create_table(
            "investment_scores",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("horizon", sa.String(8), nullable=False),
            sa.Column("profile", sa.String(32), nullable=False, server_default="Balanced"),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("band", sa.String(4), nullable=False),
            sa.Column("raw_score", sa.Float(), nullable=False),
            sa.Column("components", JSONB(), nullable=False),
            sa.Column("reprint_penalty", sa.Float(), server_default="0"),
            sa.Column("risk_penalty", sa.Float(), server_default="0"),
            sa.Column("data_coverage", sa.Float(), server_default="1"),
            sa.Column("is_sufficient", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("model_version_id", sa.Uuid(),
                      sa.ForeignKey("model_versions.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("instrument_id", "as_of_date", "horizon", "profile",
                                name="uq_score_instrument_date_horizon"),
            sa.Index("ix_scores_instrument_date", "instrument_id", "as_of_date"),
        )

    if "risk_assessments" not in existing:
        op.create_table(
            "risk_assessments",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("horizon", sa.String(8), nullable=False),
            sa.Column("overall_score", sa.Float(), nullable=False),
            sa.Column("overall_level", sa.String(16), nullable=False),
            sa.Column("factors", JSONB(), nullable=False),
            sa.Column("narrative", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("instrument_id", "as_of_date", "horizon",
                                name="uq_risk_instrument_date_horizon"),
            sa.Index("ix_risk_instrument_date", "instrument_id", "as_of_date"),
        )

    if "conformal_calibrations" not in existing:
        op.create_table(
            "conformal_calibrations",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("model_version_id", sa.Uuid(),
                      sa.ForeignKey("model_versions.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("nominal_coverage", sa.Float(), nullable=False),
            sa.Column("lo_quantile", sa.Float(), nullable=False),
            sa.Column("hi_quantile", sa.Float(), nullable=False),
            sa.Column("adjustment", sa.Float(), nullable=False),
            sa.Column("coverage_before", sa.Float(), nullable=False),
            sa.Column("coverage_after", sa.Float(), nullable=False),
            sa.Column("n_calibration", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("model_version_id", "lo_quantile", "hi_quantile",
                                name="uq_conformal_model_quantiles"),
        )


def downgrade() -> None:
    op.drop_table("conformal_calibrations")
    op.drop_table("risk_assessments")
    op.drop_table("investment_scores")
    op.drop_table("prediction_explanations")
