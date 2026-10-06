"""Phase 3 API: portfolio, watchlists, alerts, scanner, Monte Carlo, similarity, assistant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field

from pokequant.api.deps import get_session, get_settings
from pokequant.core.config import Settings
from pokequant.domain.enums import Horizon

router = APIRouter()

# Default owner (no auth yet — single-user mode).
DEFAULT_OWNER = "local"


# --------------------------------------------------------------------------- #
# Portfolio
# --------------------------------------------------------------------------- #


class TransactionCreate(BaseModel):
    instrument_id: str
    side: str = Field(pattern="^(buy|sell)$")
    quantity: int = Field(gt=0)
    price_usd: float = Field(gt=0)
    fees_usd: float = Field(default=0, ge=0)
    transacted_at: Optional[str] = None
    notes: Optional[str] = None


@router.post("/portfolio/transactions")
def add_transaction(body: TransactionCreate, session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.portfolio.service import PortfolioService

    svc = PortfolioService(session)
    portfolio = svc.get_or_create(DEFAULT_OWNER)
    txn_time = datetime.fromisoformat(body.transacted_at) if body.transacted_at else datetime.utcnow()
    txn = svc.add_transaction(
        portfolio_id=portfolio.id,
        instrument_id=uuid.UUID(body.instrument_id),
        side=body.side,
        quantity=body.quantity,
        price_usd=body.price_usd,
        fees_usd=body.fees_usd,
        transacted_at=txn_time,
        notes=body.notes,
    )
    return {"id": str(txn.id), "status": "created"}


@router.get("/portfolio")
def get_portfolio(session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.portfolio.service import PortfolioService
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.catalog import CatalogRepository

    svc = PortfolioService(session)
    portfolio = svc.get_or_create(DEFAULT_OWNER)

    # Get current prices for P&L.
    snap_repo = SnapshotRepository(session)
    cat_repo = CatalogRepository(session)
    prices: dict[str, float] = {}
    for inst in cat_repo.all_active("pokemon"):
        record = snap_repo.latest(inst.id)
        if record:
            prices[str(inst.id)] = float(record.price_usd)

    summary = svc.summary(portfolio.id, DEFAULT_OWNER, current_prices=prices)
    return {
        "portfolio_id": summary.portfolio_id,
        "name": summary.name,
        "total_cost": summary.total_cost,
        "market_value": summary.market_value,
        "unrealized_pnl": summary.unrealized_pnl,
        "unrealized_pct": summary.unrealized_pct,
        "transaction_count": summary.transaction_count,
        "holdings": [
            {
                "instrument_id": h.instrument_id,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "total_cost": h.total_cost,
                "current_price": h.current_price,
                "market_value": h.market_value,
                "unrealized_pnl": h.unrealized_pnl,
                "unrealized_pct": h.unrealized_pct,
            }
            for h in summary.holdings
        ],
    }


@router.get("/portfolio/transactions")
def list_transactions(session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.portfolio.service import PortfolioService

    svc = PortfolioService(session)
    portfolio = svc.get_or_create(DEFAULT_OWNER)
    txns = svc.get_transactions(portfolio.id)
    return {
        "transactions": [
            {
                "id": str(t.id),
                "instrument_id": str(t.instrument_id),
                "side": t.side,
                "quantity": t.quantity,
                "price_usd": float(t.price_usd),
                "fees_usd": float(t.fees_usd),
                "transacted_at": t.transacted_at.isoformat(),
                "notes": t.notes,
            }
            for t in txns
        ]
    }


# --------------------------------------------------------------------------- #
# Watchlists
# --------------------------------------------------------------------------- #


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class WatchlistAddItem(BaseModel):
    instrument_id: str


@router.post("/watchlists")
def create_watchlist(body: WatchlistCreate, session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.watchlist.service import WatchlistService
    svc = WatchlistService(session)
    wl = svc.create(DEFAULT_OWNER, body.name)
    return {"id": str(wl.id), "name": wl.name}


@router.get("/watchlists")
def list_watchlists(session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.watchlist.service import WatchlistService
    svc = WatchlistService(session)
    wls = svc.list_for_owner(DEFAULT_OWNER)
    return {
        "watchlists": [
            {"id": str(wl.id), "name": wl.name, "created_at": wl.created_at.isoformat()}
            for wl in wls
        ]
    }


@router.post("/watchlists/{watchlist_id}/items")
def add_to_watchlist(
    watchlist_id: uuid.UUID, body: WatchlistAddItem, session: Any = Depends(get_session)
) -> dict[str, Any]:
    from pokequant.watchlist.service import WatchlistService
    svc = WatchlistService(session)
    item = svc.add_instrument(watchlist_id, uuid.UUID(body.instrument_id))
    return {"id": str(item.id), "status": "added"}


@router.delete("/watchlists/{watchlist_id}/items/{instrument_id}")
def remove_from_watchlist(
    watchlist_id: uuid.UUID, instrument_id: uuid.UUID, session: Any = Depends(get_session)
) -> dict[str, str]:
    from pokequant.watchlist.service import WatchlistService
    svc = WatchlistService(session)
    svc.remove_instrument(watchlist_id, instrument_id)
    return {"status": "removed"}


@router.get("/watchlists/{watchlist_id}")
def get_watchlist(watchlist_id: uuid.UUID, session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.watchlist.service import WatchlistService
    svc = WatchlistService(session)
    wl = svc.get(watchlist_id)
    if not wl:
        return {"error": "Watchlist not found"}
    items = svc.items(watchlist_id)
    return {
        "id": str(wl.id),
        "name": wl.name,
        "items": [{"instrument_id": str(i.instrument_id), "added_at": i.added_at.isoformat()} for i in items],
    }


@router.delete("/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: uuid.UUID, session: Any = Depends(get_session)) -> dict[str, str]:
    from pokequant.watchlist.service import WatchlistService
    svc = WatchlistService(session)
    svc.delete(watchlist_id)
    return {"status": "deleted"}


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #


class AlertRuleCreate(BaseModel):
    instrument_id: str
    rule_type: str = Field(pattern="^(price_above|price_below|score_above|score_below|risk_above)$")
    threshold: float


@router.post("/alerts/rules")
def create_alert(body: AlertRuleCreate, session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.alerts.service import AlertService
    svc = AlertService(session)
    rule = svc.create_rule(DEFAULT_OWNER, uuid.UUID(body.instrument_id), body.rule_type, body.threshold)
    return {"id": str(rule.id), "rule_type": rule.rule_type, "threshold": rule.threshold}


@router.get("/alerts/rules")
def list_alert_rules(session: Any = Depends(get_session)) -> dict[str, Any]:
    from pokequant.alerts.service import AlertService
    svc = AlertService(session)
    rules = svc.list_rules(DEFAULT_OWNER)
    return {
        "rules": [
            {
                "id": str(r.id),
                "instrument_id": str(r.instrument_id),
                "rule_type": r.rule_type,
                "threshold": r.threshold,
                "is_active": r.is_active,
                "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
            }
            for r in rules
        ]
    }


@router.delete("/alerts/rules/{rule_id}")
def delete_alert_rule(rule_id: uuid.UUID, session: Any = Depends(get_session)) -> dict[str, str]:
    from pokequant.alerts.service import AlertService
    svc = AlertService(session)
    svc.delete_rule(rule_id)
    return {"status": "deleted"}


@router.get("/alerts/events")
def list_alert_events(
    unread_only: bool = Query(default=False), session: Any = Depends(get_session)
) -> dict[str, Any]:
    from pokequant.alerts.service import AlertService
    svc = AlertService(session)
    events = svc.get_events(DEFAULT_OWNER, unread_only=unread_only)
    return {
        "events": [
            {
                "id": str(e.id),
                "instrument_id": str(e.instrument_id),
                "message": e.message,
                "current_value": e.current_value,
                "is_read": e.is_read,
                "fired_at": e.fired_at.isoformat(),
            }
            for e in events
        ]
    }


@router.post("/alerts/events/{event_id}/read")
def mark_event_read(event_id: uuid.UUID, session: Any = Depends(get_session)) -> dict[str, str]:
    from pokequant.alerts.service import AlertService
    svc = AlertService(session)
    svc.mark_read(event_id)
    return {"status": "read"}


# --------------------------------------------------------------------------- #
# Scanner (rank by score / risk / momentum)
# --------------------------------------------------------------------------- #


@router.get("/scanner")
def scanner(
    sort_by: str = Query(default="score", pattern="^(score|risk|momentum|return)$"),
    limit: int = Query(default=10, ge=1, le=50),
    horizon: str = Query(default="d90"),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Rank instruments by score, risk, momentum, or expected return."""
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.ml_repo import PredictionRepository
    from pokequant.repositories.phase2_repo import RiskRepository, ScoreRepository

    catalog = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)
    score_repo = ScoreRepository(session)
    risk_repo = RiskRepository(session)
    pred_repo = PredictionRepository(session)

    instruments = catalog.all_active("pokemon")
    rows: list[dict[str, Any]] = []

    for inst in instruments:
        row: dict[str, Any] = {
            "instrument_id": str(inst.id),
            "symbol": inst.symbol,
            "name": inst.name,
        }
        # Price.
        record = snap_repo.latest(inst.id)
        row["price_usd"] = float(record.price_usd) if record else None

        # Score.
        score = score_repo.latest(inst.id, horizon)
        row["score"] = score.score if score else None
        row["band"] = score.band if score else None

        # Risk.
        risk = risk_repo.latest(inst.id, horizon)
        row["risk"] = risk.overall_score if risk else None
        row["risk_level"] = risk.overall_level if risk else None

        # Forecast.
        pred = pred_repo.latest(inst.id, horizon)
        row["expected_return"] = pred.predicted_return if pred else None
        row["predicted_price"] = float(pred.predicted_price) if pred else None

        # Momentum (from return).
        row["momentum"] = pred.predicted_return if pred else None

        rows.append(row)

    # Sort.
    def sort_key(r: dict[str, Any]) -> float:
        v = r.get(sort_by)
        if v is None:
            return float("-inf") if sort_by != "risk" else float("inf")
        return float(v)

    descending = sort_by != "risk"
    rows.sort(key=sort_key, reverse=descending)

    return {"sort_by": sort_by, "horizon": horizon, "items": rows[:limit]}


# --------------------------------------------------------------------------- #
# Monte Carlo
# --------------------------------------------------------------------------- #


@router.get("/instruments/{instrument_id}/montecarlo")
def monte_carlo(
    instrument_id: uuid.UUID,
    horizon: str = Query(default="d90"),
    n_paths: int = Query(default=10000, ge=1000, le=100000),
    target_price: Optional[float] = Query(default=None),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Run Monte Carlo simulation for an instrument."""
    from pokequant.features.builder import build_features
    from pokequant.ml.dataset import snapshots_to_frame
    from pokequant.montecarlo.engine import simulate
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.ml_repo import PredictionRepository

    snap_repo = SnapshotRepository(session)
    pred_repo = PredictionRepository(session)
    cat_repo = CatalogRepository(session)

    inst = cat_repo.get(instrument_id)
    if not inst:
        return {"error": "Instrument not found"}

    records = snap_repo.history(instrument_id)
    if not records:
        return {"error": "No price history"}

    frame = snapshots_to_frame(records)
    last_price = float(frame["price_usd"].iloc[-1])

    # Get forecast return.
    pred = pred_repo.latest(instrument_id, horizon)
    expected_return = pred.predicted_return if pred else 0.0

    # Get volatility from features.
    release = inst.release_date or frame.index[0].date()
    features_df = build_features(frame, release)
    vol = float(features_df["vol_90"].iloc[-1]) if not features_df.empty and "vol_90" in features_df else 0.25

    h = Horizon(horizon)
    targets = [target_price] if target_price else []

    result = simulate(
        last_price=last_price,
        expected_return=expected_return,
        volatility=vol,
        horizon_days=h.days,
        n_paths=n_paths,
        target_prices=targets,
    )
    return result.to_dict()


# --------------------------------------------------------------------------- #
# Similarity
# --------------------------------------------------------------------------- #


@router.get("/instruments/{instrument_id}/similar")
def find_similar_instruments(
    instrument_id: uuid.UUID,
    top_k: int = Query(default=5, ge=1, le=15),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Find instruments similar to the target based on feature vectors."""
    from pokequant.features.builder import build_features
    from pokequant.ml.dataset import snapshots_to_frame
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.similarity.engine import find_similar

    cat_repo = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)

    target = cat_repo.get(instrument_id)
    if not target:
        return {"error": "Instrument not found"}

    # Build features for all instruments.
    all_features: dict[str, dict[str, float]] = {}
    meta: dict[str, dict[str, str]] = {}
    instruments = cat_repo.all_active("pokemon")

    for inst in instruments:
        records = snap_repo.history(inst.id)
        if not records:
            continue
        frame = snapshots_to_frame(records)
        if frame.empty:
            continue
        release = inst.release_date or frame.index[0].date()
        feats = build_features(frame, release)
        if feats.empty:
            continue
        all_features[str(inst.id)] = feats.iloc[-1].to_dict()
        meta[str(inst.id)] = {"symbol": inst.symbol, "name": inst.name}

    target_feats = all_features.get(str(instrument_id))
    if not target_feats:
        return {"error": "No features for target instrument"}

    result = find_similar(
        str(instrument_id), target_feats, all_features, meta, top_k=top_k
    )
    return result.to_dict()


# --------------------------------------------------------------------------- #
# AI Assistant
# --------------------------------------------------------------------------- #


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/assistant/chat")
def assistant_chat(
    body: ChatMessage,
    session: Any = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Ask the AI research assistant a question."""
    from pokequant.assistant.llm import GroqClient
    from pokequant.assistant.service import AssistantService

    groq_key = settings.groq_api_key
    if not groq_key:
        return {
            "answer": "AI assistant is not configured. Set GROQ_API_KEY in your environment.",
            "model_used": None,
            "grounded": False,
        }

    client = GroqClient(groq_key)
    try:
        svc = AssistantService(session, client)
        response = svc.answer(body.message, owner_id=DEFAULT_OWNER)
        return response.to_dict()
    finally:
        client.close()


# --------------------------------------------------------------------------- #
# Compare
# --------------------------------------------------------------------------- #


@router.get("/compare")
def compare_instruments(
    ids: str = Query(..., description="Comma-separated instrument IDs"),
    horizon: str = Query(default="d90"),
    session: Any = Depends(get_session),
) -> dict[str, Any]:
    """Side-by-side comparison of multiple instruments."""
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.ml_repo import PredictionRepository
    from pokequant.repositories.phase2_repo import RiskRepository, ScoreRepository

    instrument_ids = [s.strip() for s in ids.split(",") if s.strip()][:5]

    cat_repo = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)
    score_repo = ScoreRepository(session)
    risk_repo = RiskRepository(session)
    pred_repo = PredictionRepository(session)

    items: list[dict[str, Any]] = []
    for iid_str in instrument_ids:
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
            "release_date": inst.release_date.isoformat() if inst.release_date else None,
        }

        record = snap_repo.latest(iid)
        item["price_usd"] = float(record.price_usd) if record else None

        score = score_repo.latest(iid, horizon)
        item["score"] = score.score if score else None
        item["band"] = score.band if score else None

        risk = risk_repo.latest(iid, horizon)
        item["risk_score"] = risk.overall_score if risk else None
        item["risk_level"] = risk.overall_level if risk else None

        pred = pred_repo.latest(iid, horizon)
        item["expected_return"] = pred.predicted_return if pred else None
        item["predicted_price"] = float(pred.predicted_price) if pred else None

        items.append(item)

    return {"horizon": horizon, "instruments": items}


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #


@router.get("/dashboard")
def dashboard(session: Any = Depends(get_session)) -> dict[str, Any]:
    """Dashboard aggregate: portfolio pulse, top movers, opportunities, alerts."""
    from pokequant.portfolio.service import PortfolioService
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.ml_repo import PredictionRepository
    from pokequant.repositories.phase2_repo import ScoreRepository

    cat_repo = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)
    score_repo = ScoreRepository(session)
    pred_repo = PredictionRepository(session)
    port_svc = PortfolioService(session)

    # Portfolio summary.
    portfolio = port_svc.get_or_create(DEFAULT_OWNER)
    prices: dict[str, float] = {}
    instruments = cat_repo.all_active("pokemon")
    for inst in instruments:
        record = snap_repo.latest(inst.id)
        if record:
            prices[str(inst.id)] = float(record.price_usd)

    port_summary = port_svc.summary(portfolio.id, DEFAULT_OWNER, current_prices=prices)

    # Top opportunities (by score).
    opportunities: list[dict[str, Any]] = []
    for inst in instruments:
        score = score_repo.latest(inst.id, "d90")
        pred = pred_repo.latest(inst.id, "d90")
        if score and score.score:
            opportunities.append({
                "instrument_id": str(inst.id),
                "symbol": inst.symbol,
                "name": inst.name,
                "score": score.score,
                "band": score.band,
                "expected_return": pred.predicted_return if pred else None,
            })
    opportunities.sort(key=lambda x: x["score"], reverse=True)

    # Market movers (by expected return).
    movers: list[dict[str, Any]] = []
    for inst in instruments:
        pred = pred_repo.latest(inst.id, "d90")
        if pred:
            movers.append({
                "instrument_id": str(inst.id),
                "symbol": inst.symbol,
                "name": inst.name,
                "expected_return": pred.predicted_return,
                "price_usd": prices.get(str(inst.id)),
            })
    movers.sort(key=lambda x: abs(x["expected_return"]), reverse=True)

    return {
        "portfolio": {
            "total_cost": port_summary.total_cost,
            "market_value": port_summary.market_value,
            "unrealized_pnl": port_summary.unrealized_pnl,
            "unrealized_pct": port_summary.unrealized_pct,
            "holdings_count": len(port_summary.holdings),
        },
        "top_opportunities": opportunities[:5],
        "market_movers": movers[:5],
        "instruments_count": len(instruments),
    }


# --------------------------------------------------------------------------- #
# Daily Summary
# --------------------------------------------------------------------------- #


@router.get("/summary")
def daily_summary(session: Any = Depends(get_session)) -> dict[str, Any]:
    """Daily market summary: what changed, key movers, risk alerts, aggregate stats."""
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.ml_repo import PredictionRepository
    from pokequant.repositories.phase2_repo import RiskRepository, ScoreRepository

    cat_repo = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)
    score_repo = ScoreRepository(session)
    risk_repo = RiskRepository(session)
    pred_repo = PredictionRepository(session)

    instruments = cat_repo.all_active("pokemon")

    # Gather all instrument data.
    bullish = 0
    bearish = 0
    high_risk_names: list[str] = []
    top_scorers: list[dict[str, Any]] = []
    biggest_movers: list[dict[str, Any]] = []

    for inst in instruments:
        pred = pred_repo.latest(inst.id, "d90")
        score = score_repo.latest(inst.id, "d90")
        risk = risk_repo.latest(inst.id, "d90")
        latest = snap_repo.latest(inst.id)

        if pred and pred.predicted_return > 0:
            bullish += 1
        elif pred and pred.predicted_return < 0:
            bearish += 1

        if risk and risk.overall_score > 60:
            high_risk_names.append(inst.symbol)

        if score and score.score:
            top_scorers.append({"symbol": inst.symbol, "score": score.score, "band": score.band})

        if pred:
            biggest_movers.append({
                "symbol": inst.symbol,
                "expected_return": pred.predicted_return,
                "price": float(latest.price_usd) if latest else None,
            })

    top_scorers.sort(key=lambda x: x["score"], reverse=True)
    biggest_movers.sort(key=lambda x: abs(x["expected_return"]), reverse=True)
    total = len(instruments)

    # Build narrative.
    breadth_pct = (bullish / total * 100) if total > 0 else 0
    narrative_parts = [
        f"Market breadth: {breadth_pct:.0f}% bullish ({bullish} of {total} instruments with positive expected return).",
    ]
    if top_scorers:
        narrative_parts.append(
            f"Top rated: {top_scorers[0]['symbol']} ({top_scorers[0]['score']:.0f} {top_scorers[0]['band']})."
        )
    if biggest_movers:
        m = biggest_movers[0]
        direction = "up" if m["expected_return"] > 0 else "down"
        narrative_parts.append(
            f"Biggest mover: {m['symbol']} (expected {direction} {abs(m['expected_return'])*100:.1f}%)."
        )
    if high_risk_names:
        narrative_parts.append(f"Elevated risk: {', '.join(high_risk_names[:3])}.")

    return {
        "total_instruments": total,
        "bullish": bullish,
        "bearish": bearish,
        "neutral": total - bullish - bearish,
        "breadth_pct": round(breadth_pct, 1),
        "high_risk_instruments": high_risk_names[:5],
        "top_scorers": top_scorers[:5],
        "biggest_movers": biggest_movers[:5],
        "narrative": " ".join(narrative_parts),
    }


# --------------------------------------------------------------------------- #
# Portfolio Review (AI-assisted)
# --------------------------------------------------------------------------- #


@router.get("/portfolio/review")
def portfolio_review(
    session: Any = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """AI-powered portfolio review: strengths, risks, suggestions."""
    from pokequant.assistant.llm import GroqClient
    from pokequant.portfolio.service import PortfolioService
    from pokequant.repositories.catalog import CatalogRepository
    from pokequant.repositories.market import SnapshotRepository
    from pokequant.repositories.phase2_repo import RiskRepository, ScoreRepository

    cat_repo = CatalogRepository(session)
    snap_repo = SnapshotRepository(session)
    score_repo = ScoreRepository(session)
    risk_repo = RiskRepository(session)
    port_svc = PortfolioService(session)

    portfolio = port_svc.get_or_create(DEFAULT_OWNER)

    # Get current prices.
    prices: dict[str, float] = {}
    instruments = cat_repo.all_active("pokemon")
    for inst in instruments:
        record = snap_repo.latest(inst.id)
        if record:
            prices[str(inst.id)] = float(record.price_usd)

    summary = port_svc.summary(portfolio.id, DEFAULT_OWNER, current_prices=prices)

    if not summary.holdings:
        return {
            "review": "Your portfolio is empty. Add transactions first.",
            "holdings_count": 0,
        }

    # Build context for the LLM.
    holding_lines: list[str] = []
    for h in summary.holdings:
        inst = cat_repo.get(uuid.UUID(h.instrument_id))
        name = inst.symbol if inst else h.instrument_id[:8]
        score_rec = score_repo.latest(uuid.UUID(h.instrument_id), "d90") if inst else None
        risk_rec = risk_repo.latest(uuid.UUID(h.instrument_id), "d90") if inst else None
        line = f"- {name}: qty={h.quantity}, cost=${h.avg_cost:.2f}, current=${h.current_price or 0:.2f}, P&L={h.unrealized_pct or 0:.1f}%"
        if score_rec:
            line += f", score={score_rec.score:.0f}({score_rec.band})"
        if risk_rec:
            line += f", risk={risk_rec.overall_score:.0f}"
        holding_lines.append(line)

    context = f"""Portfolio summary:
- Total cost: ${summary.total_cost:.2f}
- Market value: ${summary.market_value:.2f}
- Unrealized P&L: ${summary.unrealized_pnl:.2f} ({summary.unrealized_pct:.1f}%)
- Holdings ({len(summary.holdings)}):
{chr(10).join(holding_lines)}"""

    groq_key = settings.groq_api_key
    if not groq_key:
        return {
            "review": "AI review unavailable (GROQ_API_KEY not set). Portfolio data shown above.",
            "holdings_count": len(summary.holdings),
            "context": context,
        }

    client = GroqClient(groq_key)
    try:
        messages = [
            {"role": "system", "content": (
                "You are the PokéQuant portfolio advisor. Review the user's portfolio. "
                "Identify strengths, risks, concentration issues, and suggestions. "
                "Be concise (3-5 bullet points). Only use facts from the provided data. "
                "This is research, not investment advice."
            )},
            {"role": "user", "content": f"Review my portfolio:\n\n{context}"},
        ]
        review = client.chat(messages, temperature=0.3, max_tokens=500)
    finally:
        client.close()

    return {
        "review": review or "Unable to generate review (models at capacity).",
        "holdings_count": len(summary.holdings),
        "total_cost": summary.total_cost,
        "market_value": summary.market_value,
        "unrealized_pnl": summary.unrealized_pnl,
        "unrealized_pct": summary.unrealized_pct,
    }
