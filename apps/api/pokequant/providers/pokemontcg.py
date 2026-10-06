"""PokemonTCG.io adapter - catalog/reference data (sets, release dates).

In Phase 1 this source feeds the *catalog* (set metadata + release dates), not
sealed prices (which it does not provide). See docs/02-data-sources.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from pokequant.domain.entities import ProviderInfo
from pokequant.providers.base import HttpProvider
from pokequant.providers.ratelimit import TokenBucket

BASE_URL = "https://api.pokemontcg.io/v2"


@dataclass(frozen=True)
class SetInfo:
    set_id: str
    name: str
    series: str
    release_date: Optional[date]
    total: Optional[int]


def _parse_release(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_sets(payload: dict[str, Any]) -> list[SetInfo]:
    """Normalize a /sets response into SetInfo records (pure, fixture-testable)."""
    out: list[SetInfo] = []
    for item in payload.get("data", []):
        out.append(
            SetInfo(
                set_id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                series=str(item.get("series", "")),
                release_date=_parse_release(item.get("releaseDate")),
                total=item.get("total"),
            )
        )
    return out


class PokemonTcgProvider(HttpProvider):
    info = ProviderInfo(slug="pokemontcg", name="PokemonTCG.io", tier=2)

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        rate_limiter: Optional[TokenBucket] = None,
        client: object = None,
    ) -> None:
        headers = {"X-Api-Key": api_key} if api_key else {}
        super().__init__(BASE_URL, rate_limiter=rate_limiter, headers=headers, client=client)  # type: ignore[arg-type]
        self._api_key = api_key

    def available(self) -> bool:
        # Works without a key (at a lower rate limit).
        return True

    def fetch_sets(self) -> list[SetInfo]:
        payload = self._get("/sets", params={"pageSize": 250, "orderBy": "releaseDate"})
        return parse_sets(payload)

    def search_cards(self, query: str, *, page_size: int = 12) -> dict[str, Any]:
        """Search cards. `query` is matched against name (Lucene)."""
        q = query.strip()
        # Prefer name match; fall back to a loose full-text query.
        lucene = f'name:"{q}" OR name:{q}*'
        return self._get(
            "/cards",
            params={"q": lucene, "pageSize": min(page_size, 50), "orderBy": "name"},
        )

    def get_card(self, card_id: str) -> dict[str, Any]:
        return self._get(f"/cards/{card_id}")
