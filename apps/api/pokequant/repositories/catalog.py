"""Catalog repositories: asset classes, categories, instruments, identifiers."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pokequant.db.models import AssetClass, Category, Instrument, InstrumentIdentifier


class CatalogRepository:
    """Read + upsert operations over the catalog tables."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- reads -----------------------------------------------------------
    def list(
        self,
        *,
        asset_class: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> Sequence[Instrument]:
        stmt = select(Instrument).join(AssetClass)
        if asset_class:
            stmt = stmt.where(AssetClass.slug == asset_class)
        if active_only:
            stmt = stmt.where(Instrument.is_active.is_(True))
        stmt = stmt.order_by(Instrument.symbol).limit(limit).offset(offset)
        return self.session.execute(stmt).scalars().all()

    def count(self, *, asset_class: Optional[str] = None, active_only: bool = True) -> int:
        stmt = select(func.count(Instrument.id)).join(AssetClass)
        if asset_class:
            stmt = stmt.where(AssetClass.slug == asset_class)
        if active_only:
            stmt = stmt.where(Instrument.is_active.is_(True))
        return int(self.session.execute(stmt).scalar_one())

    def get(self, instrument_id: uuid.UUID) -> Optional[Instrument]:
        return self.session.get(Instrument, instrument_id)

    def get_by_symbol(self, symbol: str) -> Optional[Instrument]:
        return self.session.execute(
            select(Instrument).where(Instrument.symbol == symbol)
        ).scalar_one_or_none()

    def all_active(self, asset_class: Optional[str] = None) -> Sequence[Instrument]:
        stmt = select(Instrument).join(AssetClass).where(Instrument.is_active.is_(True))
        if asset_class:
            stmt = stmt.where(AssetClass.slug == asset_class)
        return self.session.execute(stmt.order_by(Instrument.symbol)).scalars().all()

    # -- upserts (idempotent seeding / sync) -----------------------------
    def upsert_asset_class(self, slug: str, name: str) -> AssetClass:
        stmt = (
            pg_insert(AssetClass)
            .values(slug=slug, name=name)
            .on_conflict_do_update(index_elements=[AssetClass.slug], set_={"name": name})
            .returning(AssetClass.id)
        )
        self.session.execute(stmt)
        return self.session.execute(select(AssetClass).where(AssetClass.slug == slug)).scalar_one()

    def upsert_category(self, asset_class_id: uuid.UUID, slug: str, name: str) -> Category:
        stmt = (
            pg_insert(Category)
            .values(asset_class_id=asset_class_id, slug=slug, name=name)
            .on_conflict_do_update(
                index_elements=[Category.asset_class_id, Category.slug],
                set_={"name": name},
            )
        )
        self.session.execute(stmt)
        return self.session.execute(
            select(Category).where(Category.asset_class_id == asset_class_id, Category.slug == slug)
        ).scalar_one()

    def upsert_instrument(
        self,
        *,
        asset_class_id: uuid.UUID,
        category_id: Optional[uuid.UUID],
        symbol: str,
        name: str,
        release_date: object = None,
        msrp_usd: object = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Instrument:
        values = {
            "asset_class_id": asset_class_id,
            "category_id": category_id,
            "symbol": symbol,
            "name": name,
            "release_date": release_date,
            "msrp_usd": msrp_usd,
            "attributes": attributes or {},
        }
        update = {k: v for k, v in values.items() if k != "symbol"}
        stmt = (
            pg_insert(Instrument)
            .values(**values)
            .on_conflict_do_update(index_elements=[Instrument.symbol], set_=update)
        )
        self.session.execute(stmt)
        return self.get_by_symbol(symbol)  # type: ignore[return-value]

    def upsert_identifier(self, instrument_id: uuid.UUID, source: str, external_id: str) -> None:
        stmt = (
            pg_insert(InstrumentIdentifier)
            .values(instrument_id=instrument_id, source=source, external_id=external_id)
            .on_conflict_do_update(
                index_elements=[
                    InstrumentIdentifier.instrument_id,
                    InstrumentIdentifier.source,
                ],
                set_={"external_id": external_id},
            )
        )
        self.session.execute(stmt)
