"""eBay Browse API adapter.

The Browse API exposes *active listings* (asks) - not sold prices, which eBay
does not offer via API (docs/02-data-sources.md). So we derive:
  * a LISTING price point (median ask of matching sealed items), and
  * a supply signal (active listing count).
Running this daily builds our own listing time-series ("own-your-timeseries").
"""

from __future__ import annotations

import statistics
from datetime import date, datetime
from typing import Any, Optional

import httpx

from pokequant.core.clock import utcnow
from pokequant.core.logging import get_logger
from pokequant.domain.entities import (
    InstrumentQuery,
    PricePoint,
    ProviderInfo,
    ProviderResult,
    SupplyPoint,
)
from pokequant.domain.enums import Condition, PriceKind
from pokequant.providers.base import HttpProvider
from pokequant.providers.ratelimit import TokenBucket

BASE_URL = "https://api.ebay.com"
OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_PATH = "/buy/browse/v1/item_summary/search"

log = get_logger(__name__)


def parse_search(
    payload: dict[str, Any], *, observed_at: datetime
) -> tuple[Optional[PricePoint], Optional[SupplyPoint]]:
    """Normalize an item_summary/search response (pure, fixture-testable)."""
    summaries = payload.get("itemSummaries") or []
    usd_prices: list[float] = []
    for item in summaries:
        price = item.get("price") or {}
        value, currency = price.get("value"), price.get("currency")
        if value is None or (currency and currency != "USD"):
            continue
        try:
            usd_prices.append(float(value))
        except (TypeError, ValueError):
            continue

    price_point: Optional[PricePoint] = None
    if usd_prices:
        price_point = PricePoint(
            observed_at=observed_at,
            price_usd=float(statistics.median(usd_prices)),
            kind=PriceKind.LISTING,
            condition=Condition.SEALED,
            volume=len(usd_prices),
        )

    total = payload.get("total")
    supply_point = (
        SupplyPoint(observed_at=observed_at, active_listings=int(total))
        if total is not None
        else None
    )
    return price_point, supply_point


class EbayBrowseProvider(HttpProvider):
    info = ProviderInfo(slug="ebay", name="eBay Browse", tier=2)

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        *,
        marketplace_id: str = "EBAY_US",
        rate_limiter: Optional[TokenBucket] = None,
        client: object = None,
        access_token: Optional[str] = None,
    ) -> None:
        super().__init__(
            BASE_URL,
            rate_limiter=rate_limiter,
            headers={"X-EBAY-C-MARKETPLACE-ID": marketplace_id},
            client=client,  # type: ignore[arg-type]
        )
        self._client_id = client_id
        self._client_secret = client_secret
        self._marketplace_id = marketplace_id
        self._token = access_token
        self._cache: dict[str, tuple[Optional[PricePoint], Optional[SupplyPoint]]] = {}

    def available(self) -> bool:
        return bool(self._client_id and self._client_secret) or bool(self._token)

    def _ensure_token(self) -> None:  # pragma: no cover - network path
        if self._token:
            return
        resp = httpx.post(
            OAUTH_URL,
            auth=(self._client_id or "", self._client_secret or ""),
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        self._client.headers["Authorization"] = f"Bearer {self._token}"

    def _search(self, query: InstrumentQuery) -> tuple[Optional[PricePoint], Optional[SupplyPoint]]:
        term = query.identifiers.get("ebay_query", query.name)
        if term in self._cache:
            return self._cache[term]
        self._ensure_token()
        payload = self._get(
            SEARCH_PATH,
            params={"q": term, "limit": 50, "filter": "buyingOptions:{FIXED_PRICE}"},
        )
        result = parse_search(payload, observed_at=utcnow())
        self._cache[term] = result
        return result

    def fetch_prices(
        self, query: InstrumentQuery, *, since: Optional[date] = None
    ) -> ProviderResult[PricePoint]:
        price, _ = self._search(query)
        res: ProviderResult[PricePoint] = ProviderResult(request_count=1)
        if price is not None:
            res.items.append(price)
        return res

    def fetch_supply(
        self, query: InstrumentQuery, *, since: Optional[date] = None
    ) -> ProviderResult[SupplyPoint]:
        _, supply = self._search(query)
        res: ProviderResult[SupplyPoint] = ProviderResult(request_count=0)
        if supply is not None:
            res.items.append(supply)
        return res

    def reset_cache(self) -> None:
        self._cache.clear()
