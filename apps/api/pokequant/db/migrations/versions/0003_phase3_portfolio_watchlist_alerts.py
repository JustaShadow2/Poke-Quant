"""Phase 3: portfolio, watchlists, alerts

Adds tables for:
- portfolios + portfolio_transactions
- watchlists + watchlist_items
- alert_rules + alert_events

Revision ID: 0003_phase3_portfolio_watchlist_alerts
Revises: 0002_phase2_xai_score_risk
Create Date: 2026-08-14
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_phase3"
down_revision: Union[str, None] = "0002_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(bind)
    existing = set(inspector.get_table_names())

    if "portfolios" not in existing:
        op.create_table(
            "portfolios",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("name", sa.String(128), nullable=False, server_default="Default"),
            sa.Column("owner_id", sa.String(64), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "portfolio_transactions" not in existing:
        op.create_table(
            "portfolio_transactions",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("portfolio_id", sa.Uuid(),
                      sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("instrument_id", sa.Uuid(),
                      sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("side", sa.String(4), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("price_usd", sa.Numeric(14, 2), nullable=False),
            sa.Column("fees_usd", sa.Numeric(14, 2), server_default="0"),
            sa.Column("transacted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Index("ix_txn_portfolio_date", "portfolio_id", "transacted_at"),
        )

    if "watchlists" not in existing:
        op.create_table(
            "watchlists",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("owner_id", sa.String(64), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "watchlist_items" not in existing:
        op.create_table(
            "watchlist_items",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("watchlist_id", sa.Uuid(),
                      sa.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("instrument_id", sa.Uuid(),
                      sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("watchlist_id", "instrument_id", name="uq_watchlist_instrument"),
        )

    if "alert_rules" not in existing:
        op.create_table(
            "alert_rules",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("owner_id", sa.String(64), nullable=False, index=True),
            sa.Column("instrument_id", sa.Uuid(),
                      sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("rule_type", sa.String(32), nullable=False),
            sa.Column("threshold", sa.Float(), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "alert_events" not in existing:
        op.create_table(
            "alert_events",
            sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("rule_id", sa.Uuid(),
                      sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("instrument_id", sa.Uuid(),
                      sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("current_value", sa.Float(), nullable=False),
            sa.Column("is_read", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("portfolio_transactions")
    op.drop_table("portfolios")
