"""FRED (Federal Reserve Economic Data) adapter - macro context series.

Free with an API key; generous limits. We ingest a small curated set of series
(rates, inflation, consumer sentiment, equities) for later macro features.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pokequant.domain.entities import MacroPoint, ProviderInfo, ProviderResult
from pokequant.providers.base import HttpProvider
from pokequant.providers.ratelimit import TokenBucket

BASE_URL = "https://api.stlouisfed.org/fred"

# Curated macro series (docs/02-data-sources.md, docs/04-feature-engineering.md).
DEFAULT_SERIES: tuple[str, ...] = ("DFF", "CPIAUCSL", "UMCSENT", "SP500")


def parse_observations(payload: dict[str, Any], series_id: str) -> list[MacroPoint]:
    """Normalize a /series/observations response (pure, fixture-testable)."""
    out: list[MacroPoint] = []
    for obs in payload.get("observations", []):
        raw_value, raw_date = obs.get("value"), obs.get("date")
        if raw_value in (None, ".", ""):
            continue
        try:
            value = float(raw_value)
            observed = datetime.strptime(raw_date, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        out.append(MacroPoint(series_id=series_id, observed_at=observed, value=value))
    return out


class FredProvider(HttpProvider):
    info = ProviderInfo(slug="fred", name="FRED", tier=1)

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        rate_limiter: Optional[TokenBucket] = None,
        client: object = None,
    ) -> None:
        super().__init__(BASE_URL, rate_limiter=rate_limiter, client=client)  # type: ignore[arg-type]
        self._api_key = api_key

    def available(self) -> bool:
        return bool(self._api_key)

    def fetch_series(
        self, series_id: str, *, since: Optional[date] = None
    ) -> ProviderResult[MacroPoint]:
        params = {"series_id": series_id, "api_key": self._api_key, "file_type": "json"}
        if since is not None:
            params["observation_start"] = since.isoformat()
        payload = self._get("/series/observations", params=params)
        items = parse_observations(payload, series_id)
        return ProviderResult(items=items, request_count=1)
