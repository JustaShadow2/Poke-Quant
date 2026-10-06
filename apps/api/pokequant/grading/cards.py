"""Parse PokemonTCG.io card payloads into a grading-friendly card record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# TCGPlayer finish keys, preferred first (raw / ungraded).
_FINISH_ORDER: tuple[str, ...] = (
    "holofoil",
    "reverseHolofoil",
    "normal",
    "unlimitedHolofoil",
    "unlimited",
    "1stEditionHolofoil",
    "1stEdition",
)


@dataclass(frozen=True)
class CardRecord:
    id: str
    name: str
    set_name: str
    set_id: str
    number: str
    rarity: Optional[str]
    artist: Optional[str]
    image_small: Optional[str]
    image_large: Optional[str]
    tcgplayer_url: Optional[str]
    raw_usd: Optional[float]
    raw_finish: Optional[str]
    raw_low: Optional[float]
    raw_mid: Optional[float]
    raw_high: Optional[float]
    prices_updated_at: Optional[str]


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pick_raw_price(
    prices: dict[str, Any],
) -> tuple[Optional[float], Optional[str], dict[str, Optional[float]]]:
    """Choose the best ungraded TCGPlayer finish and return (market, finish, band)."""
    for finish in _FINISH_ORDER:
        block = prices.get(finish)
        if not isinstance(block, dict):
            continue
        market = _f(block.get("market")) or _f(block.get("mid")) or _f(block.get("low"))
        if market is None:
            continue
        band = {
            "low": _f(block.get("low")),
            "mid": _f(block.get("mid")),
            "high": _f(block.get("high")),
        }
        return market, finish, band
    return None, None, {"low": None, "mid": None, "high": None}


def parse_card(item: dict[str, Any]) -> CardRecord:
    set_block = item.get("set") or {}
    images = item.get("images") or {}
    tcg = item.get("tcgplayer") or {}
    prices = tcg.get("prices") or {}
    raw, finish, band = pick_raw_price(prices if isinstance(prices, dict) else {})
    return CardRecord(
        id=str(item.get("id", "")),
        name=str(item.get("name", "")),
        set_name=str(set_block.get("name", "")),
        set_id=str(set_block.get("id", "")),
        number=str(item.get("number", "")),
        rarity=item.get("rarity"),
        artist=item.get("artist"),
        image_small=images.get("small"),
        image_large=images.get("large"),
        tcgplayer_url=tcg.get("url"),
        raw_usd=raw,
        raw_finish=finish,
        raw_low=band["low"],
        raw_mid=band["mid"],
        raw_high=band["high"],
        prices_updated_at=tcg.get("updatedAt"),
    )


def parse_cards(payload: dict[str, Any]) -> list[CardRecord]:
    data = payload.get("data")
    if isinstance(data, list):
        return [parse_card(item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [parse_card(data)]
    return []
