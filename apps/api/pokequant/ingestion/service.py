"""Ingestion orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from pokequant.core.clock import today
from pokequant.core.logging import get_logger
from pokequant.db.models import Instrument
from pokequant.domain.entities import InstrumentQuery
from pokequant.domain.enums import PriceKind, RunStatus
from pokequant.ingestion.consolidation import PriceCandidate, pick_price
from pokequant.providers.base import MacroProvider, MarketDataProvider
from pokequant.providers.fred import DEFAULT_SERIES
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import (
    MacroRepository,
    PriceObservationRepository,
    SnapshotRepository,
)
from pokequant.repositories.runs import ProviderRunRepository
from pokequant.synthetic.generator import SyntheticParams, generate, seed_from_symbol

log = get_logger(__name__)


def params_from_instrument(inst: Instrument) -> SyntheticParams:
    attrs = inst.attributes or {}
    msrp = inst.msrp_usd if inst.msrp_usd is not None else attrs.get("msrp_usd", 100.0)
    return SyntheticParams(
        release_date=inst.release_date or date(2022, 1, 1),
        msrp_usd=float(msrp),
        out_of_print_months=float(attrs.get("out_of_print_months", 14.0)),
        long_run_multiple=float(attrs.get("long_run_multiple", 2.3)),
        hype=float(attrs.get("hype", 1.0)),
    )


def query_from_instrument(inst: Instrument) -> InstrumentQuery:
    identifiers = {ident.source: ident.external_id for ident in inst.identifiers}
    identifiers.setdefault("ebay_query", inst.name)
    return InstrumentQuery(
        instrument_id=str(inst.id),
        symbol=inst.symbol,
        name=inst.name,
        identifiers=identifiers,
    )


class IngestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog = CatalogRepository(session)
        self.obs = PriceObservationRepository(session)
        self.snap = SnapshotRepository(session)
        self.macro = MacroRepository(session)
        self.runs = ProviderRunRepository(session)

    # -- synthetic backfill (offline bootstrap) --------------------------
    def synthetic_backfill(
        self,
        *,
        asset_class: str = "pokemon",
        end: Optional[date] = None,
        start: Optional[date] = None,
    ) -> dict[str, Any]:
        end = end or today()
        run = self.runs.create("synthetic", "backfill")
        instruments = self.catalog.all_active(asset_class)
        total_obs = 0
        total_snap = 0
        for inst in instruments:
            df = generate(
                params_from_instrument(inst),
                end=end,
                start=start,
                seed=seed_from_symbol(inst.symbol),
            )
            if df.empty:
                continue
            obs_rows = []
            snap_rows = []
            for ts, row in df.iterrows():
                observed_at = ts.to_pydatetime().replace(tzinfo=timezone.utc)
                price = float(row["price_usd"])
                obs_rows.append(
                    {
                        "observed_at": observed_at,
                        "instrument_id": inst.id,
                        "source": "synthetic",
                        "kind": PriceKind.INDEX,
                        "price_usd": price,
                        "volume": int(row["volume"]),
                        "is_synthetic": True,
                        "provider_run_id": run.id,
                    }
                )
                snap_rows.append(
                    {
                        "instrument_id": inst.id,
                        "snapshot_date": ts.date(),
                        "price_usd": price,
                        "price_source": "synthetic",
                        "price_kind": PriceKind.INDEX,
                        "volume": int(row["volume"]),
                        "active_listings": int(row["active_listings"]),
                        "attention_index": float(row["attention_index"]),
                        "is_synthetic": True,
                    }
                )
            total_obs += self.obs.bulk_upsert(obs_rows)
            total_snap += self.snap.bulk_upsert(snap_rows)

        self.runs.finish(
            run,
            status=RunStatus.SUCCESS,
            records_written=total_snap,
            details={"observations": total_obs, "instruments": len(instruments)},
        )
        return {
            "instruments": len(instruments),
            "observations": total_obs,
            "snapshots": total_snap,
        }

    # -- live ingestion --------------------------------------------------
    def ingest_live(
        self,
        market_providers: Sequence[MarketDataProvider],
        macro_provider: Optional[MacroProvider] = None,
        *,
        asset_class: str = "pokemon",
    ) -> dict[str, Any]:
        run = self.runs.create("live", "ingest")
        day = today()
        instruments = self.catalog.all_active(asset_class)
        requests = 0
        obs_written = 0
        snaps_written = 0

        active_providers = [p for p in market_providers if p.available()]
        for provider in active_providers:
            reset = getattr(provider, "reset_cache", None)
            if callable(reset):
                reset()

        for inst in instruments:
            query = query_from_instrument(inst)
            candidates: list[PriceCandidate] = []
            supply: Optional[int] = None
            obs_rows = []
            for provider in active_providers:
                price_res = provider.fetch_prices(query)
                requests += price_res.request_count
                for point in price_res.items:
                    obs_rows.append(
                        {
                            "observed_at": point.observed_at,
                            "instrument_id": inst.id,
                            "source": provider.info.slug,
                            "kind": point.kind,
                            "price_usd": point.price_usd,
                            "volume": point.volume,
                            "is_synthetic": False,
                            "source_url": point.source_url,
                            "provider_run_id": run.id,
                        }
                    )
                    candidates.append(
                        PriceCandidate(
                            price_usd=point.price_usd,
                            source=provider.info.slug,
                            kind=point.kind,
                            tier=provider.info.tier,
                        )
                    )
                supply_res = provider.fetch_supply(query)
                requests += supply_res.request_count
                for sp in supply_res.items:
                    if sp.active_listings is not None:
                        supply = sp.active_listings

            if obs_rows:
                obs_written += self.obs.bulk_upsert(obs_rows)
            if candidates:
                best = pick_price(candidates)
                snaps_written += self.snap.bulk_upsert(
                    [
                        {
                            "instrument_id": inst.id,
                            "snapshot_date": day,
                            "price_usd": best.price_usd,
                            "price_source": best.source,
                            "price_kind": best.kind,
                            "active_listings": supply,
                            "is_synthetic": False,
                        }
                    ]
                )

        macro_written = self._ingest_macro(macro_provider)
        requests += macro_written["requests"]

        status = RunStatus.SUCCESS if active_providers else RunStatus.SKIPPED
        self.runs.finish(
            run,
            status=status,
            records_written=snaps_written,
            request_count=requests,
            message=None if active_providers else "no market providers configured",
            details={
                "providers": [p.info.slug for p in active_providers],
                "observations": obs_written,
                "macro_points": macro_written["points"],
            },
        )
        return {
            "providers": [p.info.slug for p in active_providers],
            "observations": obs_written,
            "snapshots": snaps_written,
            "macro_points": macro_written["points"],
            "requests": requests,
        }

    def _ingest_macro(self, macro_provider: Optional[MacroProvider]) -> dict[str, int]:
        if macro_provider is None or not macro_provider.available():
            return {"points": 0, "requests": 0}
        points = 0
        requests = 0
        for series_id in DEFAULT_SERIES:
            result = macro_provider.fetch_series(series_id)
            requests += result.request_count
            rows = [
                {
                    "series_id": mp.series_id,
                    "observed_at": mp.observed_at.date(),
                    "value": mp.value,
                }
                for mp in result.items
            ]
            points += self.macro.bulk_upsert(rows)
        return {"points": points, "requests": requests}
