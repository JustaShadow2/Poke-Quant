"""initial Phase-1 schema + TimescaleDB hypertable

Baseline migration: the schema is created from the ORM metadata (single source of
truth), then TimescaleDB-specific DDL is applied conditionally so the same
migration also runs on a vanilla Postgres instance (e.g. lightweight CI).

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-01
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

from pokequant.db import models  # noqa: F401  (register tables on metadata)
from pokequant.db.base import Base

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ENABLE_EXTENSIONS = """
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS timescaledb;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'timescaledb extension unavailable, continuing without it: %', SQLERRM;
    END;
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'pgvector extension unavailable, continuing without it: %', SQLERRM;
    END;
END $$;
"""

_MAKE_HYPERTABLE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'price_observations', 'observed_at',
            chunk_time_interval => INTERVAL '30 days',
            if_not_exists => TRUE, migrate_data => TRUE
        );
    END IF;
END $$;
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(_ENABLE_EXTENSIONS)
    Base.metadata.create_all(bind=bind)
    op.execute(_MAKE_HYPERTABLE)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
