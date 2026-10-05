"""Provider ports + a shared HTTP base with retry and rate limiting."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Protocol, runtime_checkable

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pokequant.core.errors import ProviderError
from pokequant.core.logging import get_logger
from pokequant.domain.entities import (
    InstrumentQuery,
    MacroPoint,
    PricePoint,
    ProviderInfo,
    ProviderResult,
    SupplyPoint,
)
from pokequant.providers.ratelimit import TokenBucket

log = get_logger(__name__)


@runtime_checkable
class MarketDataProvider(Protocol):
    """A source of price (and optionally supply) observations for an instrument."""

    info: ProviderInfo

    def available(self) -> bool: ...

    def fetch_prices(
        self, query: InstrumentQuery, *, since: Optional[date] = None
    ) -> ProviderResult[PricePoint]: ...

    def fetch_supply(
        self, query: InstrumentQuery, *, since: Optional[date] = None
    ) -> ProviderResult[SupplyPoint]: ...


@runtime_checkable
class MacroProvider(Protocol):
    info: ProviderInfo

    def available(self) -> bool: ...

    def fetch_series(
        self, series_id: str, *, since: Optional[date] = None
    ) -> ProviderResult[MacroPoint]: ...


class HttpProvider:
    """Shared HTTP machinery: a client, retry policy and an optional rate limiter."""

    def __init__(
        self,
        base_url: str,
        *,
        rate_limiter: Optional[TokenBucket] = None,
        timeout: float = 15.0,
        headers: Optional[dict[str, str]] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url
        self._rate_limiter = rate_limiter
        self._client = client or httpx.Client(
            base_url=base_url, timeout=timeout, headers=headers or {}
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    def _get(self, path: str, *, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()
        try:
            resp = self._client.get(path, params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network path
            log.warning("provider_http_error", path=path, status=exc.response.status_code)
            raise
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise ProviderError(f"HTTP request failed: {exc}") from exc

    def close(self) -> None:
        self._client.close()
