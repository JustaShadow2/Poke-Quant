"""Consolidate multiple same-day observations into one 'best' daily price.

Preference order: realized sales > consolidated market > listing/ask > index,
tie-broken by source reliability tier (lower is better). This keeps the
`daily_snapshots` series clean while `price_observations` keeps everything raw.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokequant.domain.enums import PriceKind

_KIND_PRIORITY = {
    PriceKind.SALE: 3,
    PriceKind.MARKET: 2,
    PriceKind.LISTING: 1,
    PriceKind.INDEX: 0,
}


@dataclass(frozen=True)
class PriceCandidate:
    price_usd: float
    source: str
    kind: PriceKind
    tier: int


def pick_price(candidates: list[PriceCandidate]) -> PriceCandidate:
    """Return the highest-confidence candidate."""
    if not candidates:
        raise ValueError("no candidates to consolidate")
    return max(candidates, key=lambda c: (_KIND_PRIORITY[c.kind], -c.tier))
