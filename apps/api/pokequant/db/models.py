"""SQLAlchemy ORM models - Phase 1 subset of docs/03-database-design.md.

Design highlights:
* Asset-class-agnostic core (asset_classes -> categories -> instruments) so new
  asset classes are data, not code.
* `price_observations` is the append-only, high-volume source of truth (a
  TimescaleDB hypertable); `daily_snapshots` is the consolidated 1-row-per-day
  series that features/ML consume ("own-your-timeseries").
* Enums stored as VARCHAR+CHECK for painless migrations.

Not `from __future__ import annotations` here: SQLAlchemy resolves ``Mapped[...]``
annotations at class-creation time and concrete types are the most robust.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pokequant.core.ids import uuid7
from pokequant.db.base import Base
from pokequant.db.types import Money, pg_enum
from pokequant.domain.enums import Condition, ModelStage, PriceKind, RunStatus

_JSON_EMPTY = sa.text("'{}'::jsonb")


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(sa.Uuid, primary_key=True, default=uuid7)


def _created_at() -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #
class AssetClass(Base):
    __tablename__ = "asset_classes"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(sa.String(128))
    created_at: Mapped[datetime] = _created_at()

    categories: Mapped[list["Category"]] = relationship(
        back_populates="asset_class", cascade="all, delete-orphan"
    )
    instruments: Mapped[list["Instrument"]] = relationship(back_populates="asset_class")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (sa.UniqueConstraint("asset_class_id", "slug"),)

    id: Mapped[uuid.UUID] = _pk()
    asset_class_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("asset_classes.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(sa.String(64))
    name: Mapped[str] = mapped_column(sa.String(128))
    created_at: Mapped[datetime] = _created_at()

    asset_class: Mapped[AssetClass] = relationship(back_populates="categories")
    instruments: Mapped[list["Instrument"]] = relationship(back_populates="category")


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = _pk()
    asset_class_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("asset_classes.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    symbol: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(sa.String(256))
    release_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    msrp_usd: Mapped[Optional[Decimal]] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(sa.String(3), server_default="USD")
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=_JSON_EMPTY
    )
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    asset_class: Mapped[AssetClass] = relationship(back_populates="instruments")
    category: Mapped[Optional[Category]] = relationship(back_populates="instruments")
    identifiers: Mapped[list["InstrumentIdentifier"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )


class InstrumentIdentifier(Base):
    """Maps an instrument to source-specific keys/queries (docs/02-data-sources.md)."""

    __tablename__ = "instrument_identifiers"
    __table_args__ = (sa.UniqueConstraint("instrument_id", "source"),)

    id: Mapped[uuid.UUID] = _pk()
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(sa.String(32))
    external_id: Mapped[str] = mapped_column(sa.String(256))
    created_at: Mapped[datetime] = _created_at()

    instrument: Mapped[Instrument] = relationship(back_populates="identifiers")


# --------------------------------------------------------------------------- #
# Market / alternative data
# --------------------------------------------------------------------------- #
class PriceObservation(Base):
    """Append-only raw price observations (TimescaleDB hypertable)."""

    __tablename__ = "price_observations"
    __table_args__ = (
        sa.PrimaryKeyConstraint("observed_at", "id", name="pk_price_observations"),
        sa.UniqueConstraint(
            "instrument_id",
            "source",
            "kind",
            "condition",
            "observed_at",
            name="uq_price_observations_dedupe",
        ),
        sa.Index("ix_price_observations_instrument_time", "instrument_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    kind: Mapped[PriceKind] = mapped_column(pg_enum(PriceKind, "price_kind"), nullable=False)
    condition: Mapped[Condition] = mapped_column(
        pg_enum(Condition, "condition"), server_default=Condition.SEALED.value
    )
    price_usd: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), server_default="USD")
    volume: Mapped[Optional[int]] = mapped_column(sa.Integer)
    is_synthetic: Mapped[bool] = mapped_column(server_default=sa.false())
    source_url: Mapped[Optional[str]] = mapped_column(sa.String(1024))
    provider_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("provider_runs.id", ondelete="SET NULL")
    )
    ingested_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class DailySnapshot(Base):
    """Consolidated 1-row-per-instrument-per-day series (feature/ML input)."""

    __tablename__ = "daily_snapshots"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    snapshot_date: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    price_usd: Mapped[Decimal] = mapped_column(Money, nullable=False)
    price_source: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    price_kind: Mapped[PriceKind] = mapped_column(
        pg_enum(PriceKind, "price_kind"), server_default=PriceKind.MARKET.value
    )
    volume: Mapped[Optional[int]] = mapped_column(sa.Integer)
    active_listings: Mapped[Optional[int]] = mapped_column(sa.Integer)
    attention_index: Mapped[Optional[float]] = mapped_column(sa.Float)
    is_synthetic: Mapped[bool] = mapped_column(server_default=sa.false())
    created_at: Mapped[datetime] = _created_at()


class MacroSeriesValue(Base):
    __tablename__ = "macro_series_values"

    series_id: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    observed_at: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    value: Mapped[float] = mapped_column(sa.Numeric(18, 6), nullable=False)
    created_at: Mapped[datetime] = _created_at()


# --------------------------------------------------------------------------- #
# Feature store
# --------------------------------------------------------------------------- #
class FeatureValue(Base):
    __tablename__ = "feature_values"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    as_of_date: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    feature_set: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()


# --------------------------------------------------------------------------- #
# Model lifecycle
# --------------------------------------------------------------------------- #
class Model(Base):
    __tablename__ = "models"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True)
    asset_class: Mapped[str] = mapped_column(sa.String(64))
    kind: Mapped[str] = mapped_column(sa.String(32))
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _created_at()

    versions: Mapped[list["ModelVersion"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (sa.UniqueConstraint("model_id", "version"),)

    id: Mapped[uuid.UUID] = _pk()
    model_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("models.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(sa.String(32))
    stage: Mapped[ModelStage] = mapped_column(
        pg_enum(ModelStage, "model_stage"), server_default=ModelStage.NONE.value
    )
    horizon: Mapped[str] = mapped_column(sa.String(8))
    backend: Mapped[str] = mapped_column(sa.String(32))
    feature_set: Mapped[str] = mapped_column(sa.String(32))
    artifact_uri: Mapped[Optional[str]] = mapped_column(sa.String(1024))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_JSON_EMPTY)
    trained_on_synthetic: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[datetime] = _created_at()

    model: Mapped[Model] = relationship(back_populates="versions")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        sa.UniqueConstraint("instrument_id", "model_version_id", "horizon", "as_of_date"),
        sa.Index("ix_predictions_instrument_horizon", "instrument_id", "horizon"),
    )

    id: Mapped[uuid.UUID] = _pk()
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False
    )
    horizon: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    last_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    predicted_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    predicted_return: Mapped[float] = mapped_column(sa.Float, nullable=False)
    quantiles: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=_JSON_EMPTY
    )
    is_synthetic: Mapped[bool] = mapped_column(server_default=sa.false())
    created_at: Mapped[datetime] = _created_at()

    model_version: Mapped["ModelVersion"] = relationship(lazy="joined")


# --------------------------------------------------------------------------- #
# Operations / observability
# --------------------------------------------------------------------------- #
class ProviderRun(Base):
    __tablename__ = "provider_runs"

    id: Mapped[uuid.UUID] = _pk()
    provider: Mapped[str] = mapped_column(sa.String(32), index=True)
    run_type: Mapped[str] = mapped_column(sa.String(32))
    status: Mapped[RunStatus] = mapped_column(pg_enum(RunStatus, "run_status"))
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    records_written: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    request_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    message: Mapped[Optional[str]] = mapped_column(sa.Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_JSON_EMPTY)


# --------------------------------------------------------------------------- #
# Phase 2 — Explainability, Scores, Risk
# --------------------------------------------------------------------------- #


class PredictionExplanation(Base):
    """SHAP-based explanation stored per prediction."""

    __tablename__ = "prediction_explanations"
    __table_args__ = (
        sa.UniqueConstraint("prediction_id", name="uq_explanation_prediction"),
    )

    id: Mapped[uuid.UUID] = _pk()
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("predictions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    horizon: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    base_value: Mapped[float] = mapped_column(sa.Float, nullable=False)
    # Full attribution vector: {feature_name: shap_value}
    attributions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Top positive/negative drivers for quick access.
    top_positive: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    top_negative: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    narrative: Mapped[Optional[str]] = mapped_column(sa.Text)
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("model_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created_at()


class InvestmentScoreRecord(Base):
    """Persisted Investment Score per instrument per date."""

    __tablename__ = "investment_scores"
    __table_args__ = (
        sa.UniqueConstraint("instrument_id", "as_of_date", "horizon", "profile",
                            name="uq_score_instrument_date_horizon"),
        sa.Index("ix_scores_instrument_date", "instrument_id", "as_of_date"),
    )

    id: Mapped[uuid.UUID] = _pk()
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    horizon: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    profile: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="Balanced")
    score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    band: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    raw_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    # Component breakdown: [{name, percentile, weight, contribution, direction}]
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reprint_penalty: Mapped[float] = mapped_column(sa.Float, server_default="0")
    risk_penalty: Mapped[float] = mapped_column(sa.Float, server_default="0")
    data_coverage: Mapped[float] = mapped_column(sa.Float, server_default="1")
    is_sufficient: Mapped[bool] = mapped_column(server_default=sa.true())
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("model_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created_at()


class RiskAssessmentRecord(Base):
    """Persisted risk assessment per instrument per date."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        sa.UniqueConstraint("instrument_id", "as_of_date", "horizon",
                            name="uq_risk_instrument_date_horizon"),
        sa.Index("ix_risk_instrument_date", "instrument_id", "as_of_date"),
    )

    id: Mapped[uuid.UUID] = _pk()
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    horizon: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    overall_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    overall_level: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    # Factor details: [{name, probability, severity, score, level, narrative}]
    factors: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    narrative: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _created_at()


class ConformalCalibration(Base):
    """Stored conformal calibration state per model version."""

    __tablename__ = "conformal_calibrations"
    __table_args__ = (
        sa.UniqueConstraint("model_version_id", "lo_quantile", "hi_quantile",
                            name="uq_conformal_model_quantiles"),
    )

    id: Mapped[uuid.UUID] = _pk()
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nominal_coverage: Mapped[float] = mapped_column(sa.Float, nullable=False)
    lo_quantile: Mapped[float] = mapped_column(sa.Float, nullable=False)
    hi_quantile: Mapped[float] = mapped_column(sa.Float, nullable=False)
    adjustment: Mapped[float] = mapped_column(sa.Float, nullable=False)
    coverage_before: Mapped[float] = mapped_column(sa.Float, nullable=False)
    coverage_after: Mapped[float] = mapped_column(sa.Float, nullable=False)
    n_calibration: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = _created_at()


# --------------------------------------------------------------------------- #
# Phase 3 — Portfolio, Watchlists, Alerts, Similarity
# --------------------------------------------------------------------------- #


class Portfolio(Base):
    """A user's portfolio (no auth yet — identified by a local session ID)."""

    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, server_default="Default")
    owner_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = _created_at()


class PortfolioTransaction(Base):
    """Buy/sell transaction in a portfolio."""

    __tablename__ = "portfolio_transactions"
    __table_args__ = (
        sa.Index("ix_txn_portfolio_date", "portfolio_id", "transacted_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    side: Mapped[str] = mapped_column(sa.String(4), nullable=False)  # "buy" or "sell"
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    price_usd: Mapped[Decimal] = mapped_column(Money, nullable=False)
    fees_usd: Mapped[Decimal] = mapped_column(Money, server_default="0")
    transacted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _created_at()


class Watchlist(Base):
    """A named watchlist."""

    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    owner_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = _created_at()


class WatchlistItem(Base):
    """An instrument on a watchlist."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        sa.UniqueConstraint("watchlist_id", "instrument_id", name="uq_watchlist_instrument"),
    )

    id: Mapped[uuid.UUID] = _pk()
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = _created_at()


class AlertRule(Base):
    """A user-defined alert rule."""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    # e.g. "price_above", "price_below", "score_above", "score_below", "risk_above"
    threshold: Mapped[float] = mapped_column(sa.Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class AlertEvent(Base):
    """A fired alert notification."""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = _pk()
    rule_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    current_value: Mapped[float] = mapped_column(sa.Float, nullable=False)
    is_read: Mapped[bool] = mapped_column(server_default=sa.false())
    fired_at: Mapped[datetime] = _created_at()
