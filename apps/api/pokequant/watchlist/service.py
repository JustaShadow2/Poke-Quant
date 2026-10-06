"""Watchlist CRUD service."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pokequant.db.models import Watchlist, WatchlistItem


class WatchlistService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, owner_id: str, name: str) -> Watchlist:
        wl = Watchlist(owner_id=owner_id, name=name)
        self.session.add(wl)
        self.session.flush()
        return wl

    def list_for_owner(self, owner_id: str) -> list[Watchlist]:
        stmt = select(Watchlist).where(Watchlist.owner_id == owner_id).order_by(Watchlist.created_at)
        return list(self.session.execute(stmt).scalars().all())

    def get(self, watchlist_id: uuid.UUID) -> Optional[Watchlist]:
        return self.session.get(Watchlist, watchlist_id)

    def delete(self, watchlist_id: uuid.UUID) -> None:
        wl = self.session.get(Watchlist, watchlist_id)
        if wl:
            self.session.delete(wl)

    def add_instrument(self, watchlist_id: uuid.UUID, instrument_id: uuid.UUID) -> WatchlistItem:
        item = WatchlistItem(watchlist_id=watchlist_id, instrument_id=instrument_id)
        self.session.add(item)
        self.session.flush()
        return item

    def remove_instrument(self, watchlist_id: uuid.UUID, instrument_id: uuid.UUID) -> None:
        stmt = delete(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.instrument_id == instrument_id,
        )
        self.session.execute(stmt)

    def items(self, watchlist_id: uuid.UUID) -> list[WatchlistItem]:
        stmt = (
            select(WatchlistItem)
            .where(WatchlistItem.watchlist_id == watchlist_id)
            .order_by(WatchlistItem.added_at)
        )
        return list(self.session.execute(stmt).scalars().all())
