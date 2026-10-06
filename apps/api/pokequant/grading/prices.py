"""Estimated PSA 9 / PSA 10 prices from raw TCGPlayer + rarity.

Live graded comps are not available from PokemonTCG.io. Until PriceCharting or
Pokemon Price Tracker is wired, we publish transparent multiples and label them
as estimates (PROGRESS.md roadblock #2).
"""

from __future__ import annotations

import math
from typing import Optional

# Typical modern PSA-10 / raw multiples by rarity. Compressed for expensive cards.
_PSA10_MULTIPLE: dict[str, float] = {
    "Common": 14.0,
    "Uncommon": 11.0,
    "Rare": 4.2,
    "Rare Holo": 3.6,
    "Rare Holo EX": 3.2,
    "Rare Holo GX": 3.2,
    "Rare Holo V": 3.0,
    "Rare Holo VMAX": 2.8,
    "Rare Ultra": 2.8,
    "Ultra Rare": 2.8,
    "Double Rare": 2.6,
    "Illustration Rare": 2.7,
    "Special Illustration Rare": 2.4,
    "Hyper Rare": 2.2,
    "Secret Rare": 2.5,
    "Amazing Rare": 3.0,
    "Promo": 3.5,
}


def _psa10_multiple(raw_usd: float, rarity: Optional[str]) -> float:
    base = _PSA10_MULTIPLE.get(rarity or "", 2.9)
    # log10(1)=0 keeps base; log10(201)~2.3 compresses toward ~1.6-2.0x
    t = math.log10(max(raw_usd, 0.25) + 1.0)
    compressed = 1.25 + (base - 1.25) / (1.0 + 0.85 * t)
    return max(1.35, compressed)


def estimate_graded_prices(raw_usd: float, rarity: Optional[str]) -> dict[str, float]:
    """Return estimated PSA 9 and PSA 10 USD prices given an ungraded market price."""
    if raw_usd <= 0:
        raise ValueError("raw_usd must be positive")
    psa10 = raw_usd * _psa10_multiple(raw_usd, rarity)
    # PSA 9 sits between raw and PSA 10; modern 9s are often close to raw on cheap cards
    # and a modest premium on hits.
    gap = psa10 - raw_usd
    psa9 = raw_usd + 0.32 * gap
    psa8 = max(raw_usd * 0.9, raw_usd + 0.08 * gap)
    return {
        "psa8_usd": round(psa8, 2),
        "psa9_usd": round(psa9, 2),
        "psa10_usd": round(psa10, 2),
    }
