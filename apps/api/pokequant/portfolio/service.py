"""Portfolio service: holdings derivation and P&L computation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pokequant.db.models import Portfolio, PortfolioTransaction


@dataclass
class Holding:
    instrument_id: str
    quantity: int
    avg_cost: float
    total_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pct: Optional[float] = None


@dataclass
class PortfolioSummary:
    portfolio_id: str
    name: str
    total_cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pct: float = 0.0
    holdings: list[Holding] = field(default_factory=list)
    transaction_count: int = 0


class PortfolioService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, owner_id: str, name: str = "Default") -> Portfolio:
        stmt = select(Portfolio).where(
            Portfolio.owner_id == owner_id, Portfolio.name == name
        )
        p = self.session.execute(stmt).scalar_one_or_none()
        if p:
            return p
        p = Portfolio(owner_id=owner_id, name=name)
        self.session.add(p)
        self.session.flush()
        return p

    def list_portfolios(self, owner_id: str) -> list[Portfolio]:
        stmt = select(Portfolio).where(Portfolio.owner_id == owner_id).order_by(Portfolio.created_at)
        return list(self.session.execute(stmt).scalars().all())

    def add_transaction(
        self,
        portfolio_id: uuid.UUID,
        instrument_id: uuid.UUID,
        side: str,
        quantity: int,
        price_usd: float,
        fees_usd: float = 0.0,
        transacted_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> PortfolioTransaction:
        txn = PortfolioTransaction(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price_usd=Decimal(str(round(price_usd, 2))),
            fees_usd=Decimal(str(round(fees_usd, 2))),
            transacted_at=transacted_at or datetime.utcnow(),
            notes=notes,
        )
        self.session.add(txn)
        self.session.flush()
        return txn

    def get_transactions(self, portfolio_id: uuid.UUID) -> list[PortfolioTransaction]:
        stmt = (
            select(PortfolioTransaction)
            .where(PortfolioTransaction.portfolio_id == portfolio_id)
            .order_by(PortfolioTransaction.transacted_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def compute_holdings(
        self, portfolio_id: uuid.UUID, current_prices: Optional[dict[str, float]] = None
    ) -> list[Holding]:
        """Derive holdings from transaction history (FIFO cost basis)."""
        txns = self.get_transactions(portfolio_id)
        prices = current_prices or {}

        # Aggregate by instrument.
        agg: dict[str, dict[str, Any]] = {}
        for txn in reversed(txns):  # oldest first
            iid = str(txn.instrument_id)
            if iid not in agg:
                agg[iid] = {"qty": 0, "cost": 0.0}
            if txn.side == "buy":
                agg[iid]["qty"] += txn.quantity
                agg[iid]["cost"] += float(txn.price_usd) * txn.quantity + float(txn.fees_usd)
            elif txn.side == "sell":
                # Reduce quantity, reduce cost proportionally.
                prev_qty = agg[iid]["qty"]
                sold = min(txn.quantity, prev_qty)
                if prev_qty > 0:
                    cost_per_unit = agg[iid]["cost"] / prev_qty
                    agg[iid]["cost"] -= cost_per_unit * sold
                agg[iid]["qty"] -= sold

        holdings: list[Holding] = []
        for iid, data in agg.items():
            if data["qty"] <= 0:
                continue
            qty = data["qty"]
            total_cost = data["cost"]
            avg_cost = total_cost / qty if qty > 0 else 0
            current = prices.get(iid)
            mv = current * qty if current else None
            pnl = (mv - total_cost) if mv is not None else None
            pct = (pnl / total_cost * 100) if pnl is not None and total_cost > 0 else None
            holdings.append(Holding(
                instrument_id=iid,
                quantity=qty,
                avg_cost=round(avg_cost, 2),
                total_cost=round(total_cost, 2),
                current_price=current,
                market_value=round(mv, 2) if mv else None,
                unrealized_pnl=round(pnl, 2) if pnl is not None else None,
                unrealized_pct=round(pct, 2) if pct is not None else None,
            ))
        return holdings

    def summary(
        self, portfolio_id: uuid.UUID, owner_id: str, current_prices: Optional[dict[str, float]] = None
    ) -> PortfolioSummary:
        portfolio = self.session.get(Portfolio, portfolio_id)
        if not portfolio:
            return PortfolioSummary(portfolio_id=str(portfolio_id), name="Unknown")

        holdings = self.compute_holdings(portfolio_id, current_prices)
        total_cost = sum(h.total_cost for h in holdings)
        market_value = sum(h.market_value or h.total_cost for h in holdings)
        pnl = market_value - total_cost
        pct = (pnl / total_cost * 100) if total_cost > 0 else 0.0
        txn_count = len(self.get_transactions(portfolio_id))

        return PortfolioSummary(
            portfolio_id=str(portfolio_id),
            name=portfolio.name,
            total_cost=round(total_cost, 2),
            market_value=round(market_value, 2),
            unrealized_pnl=round(pnl, 2),
            unrealized_pct=round(pct, 2),
            holdings=holdings,
            transaction_count=txn_count,
        )
