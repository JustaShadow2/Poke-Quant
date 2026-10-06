"""Grading application service: search cards, price them, compute ROI."""

from __future__ import annotations

from typing import Any, Optional

from pokequant.core.config import Settings, get_settings
from pokequant.core.errors import NotFoundError, ProviderError, ValidationAppError
from pokequant.grading.cards import CardRecord, parse_card, parse_cards
from pokequant.grading.prices import estimate_graded_prices
from pokequant.grading.roi import DEFAULT_GRADING_FEE, DEFAULT_SHIPPING, GradeROI, compute_roi
from pokequant.grading.vision import VisionGrade, grade_image, vision_to_dict
from pokequant.providers.pokemontcg import PokemonTcgProvider
from pokequant.providers.ratelimit import TokenBucket


def roi_to_dict(roi: GradeROI) -> dict[str, Any]:
    return {
        "raw_usd": roi.raw_usd,
        "psa8_usd": roi.psa8_usd,
        "psa9_usd": roi.psa9_usd,
        "psa10_usd": roi.psa10_usd,
        "grading_fee_usd": roi.grading_fee_usd,
        "shipping_usd": roi.shipping_usd,
        "all_in_cost_usd": roi.all_in_cost_usd,
        "p10": roi.p10,
        "p9": roi.p9,
        "p8": roi.p8,
        "expected_grade_proceeds": roi.expected_grade_proceeds,
        "expected_net_vs_raw": roi.expected_net_vs_raw,
        "breakeven_p10": roi.breakeven_p10,
        "verdict": roi.verdict,
        "rationale": roi.rationale,
        "prices_are_estimated": roi.prices_are_estimated,
        "probs_source": roi.probs_source,
    }


def card_to_dict(card: CardRecord) -> dict[str, Any]:
    return {
        "id": card.id,
        "name": card.name,
        "set_name": card.set_name,
        "set_id": card.set_id,
        "number": card.number,
        "rarity": card.rarity,
        "artist": card.artist,
        "image_small": card.image_small,
        "image_large": card.image_large,
        "tcgplayer_url": card.tcgplayer_url,
        "raw_usd": card.raw_usd,
        "raw_finish": card.raw_finish,
        "raw_low": card.raw_low,
        "raw_mid": card.raw_mid,
        "raw_high": card.raw_high,
        "prices_updated_at": card.prices_updated_at,
        "raw_source": "pokemontcg.tcgplayer" if card.raw_usd is not None else None,
        "graded_source": "estimated_multiples",
    }


class GradingService:
    def __init__(self, provider: PokemonTcgProvider) -> None:
        self.provider = provider

    @classmethod
    def from_settings(cls, settings: Optional[Settings] = None) -> GradingService:
        settings = settings or get_settings()
        provider = PokemonTcgProvider(
            settings.pokemontcg_api_key,
            rate_limiter=TokenBucket(rate_per_sec=4.0, capacity=8.0),
        )
        return cls(provider)

    def search(self, query: str, *, page_size: int = 12) -> list[CardRecord]:
        q = query.strip()
        if len(q) < 2:
            raise ValidationAppError("Search query must be at least 2 characters.")
        payload = self.provider.search_cards(q, page_size=page_size)
        return parse_cards(payload)

    def get(self, card_id: str) -> CardRecord:
        try:
            payload = self.provider.get_card(card_id)
        except Exception as exc:  # httpx.HTTPStatusError among others
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 404:
                raise NotFoundError(f"Card {card_id} not found") from exc
            raise ProviderError(f"PokemonTCG.io request failed: {exc}") from exc
        data = payload.get("data")
        if not isinstance(data, dict):
            raise NotFoundError(f"Card {card_id} not found")
        card = parse_card(data)
        if not card.id:
            raise NotFoundError(f"Card {card_id} not found")
        return card

    def priced_card(
        self,
        card_id: str,
        *,
        grading_fee_usd: float = DEFAULT_GRADING_FEE,
        shipping_usd: float = DEFAULT_SHIPPING,
        predicted_grade: Optional[float] = None,
    ) -> dict[str, Any]:
        card = self.get(card_id)
        if card.raw_usd is None or card.raw_usd <= 0:
            raise ProviderError(
                "No TCGPlayer raw market price is available for this card.",
                details={"card_id": card_id},
            )
        graded = estimate_graded_prices(card.raw_usd, card.rarity)
        roi = compute_roi(
            raw_usd=card.raw_usd,
            psa9_usd=graded["psa9_usd"],
            psa10_usd=graded["psa10_usd"],
            psa8_usd=graded["psa8_usd"],
            grading_fee_usd=grading_fee_usd,
            shipping_usd=shipping_usd,
            predicted_grade=predicted_grade,
            prices_are_estimated=True,
        )
        return {
            "card": card_to_dict(card),
            "prices": {
                "raw_usd": card.raw_usd,
                "psa9_usd": graded["psa9_usd"],
                "psa10_usd": graded["psa10_usd"],
                "psa8_usd": graded["psa8_usd"],
                "raw_source": "pokemontcg.tcgplayer",
                "graded_source": "estimated_multiples",
                "graded_note": (
                    "PSA 9/10 are model estimates from raw TCGPlayer + rarity. "
                    "Live graded comps need PriceCharting or Pokemon Price Tracker."
                ),
            },
            "roi": roi_to_dict(roi),
        }

    def vision_grade(self, front: bytes, back: Optional[bytes] = None) -> dict[str, object]:
        if not front:
            raise ValidationAppError("Front image is required.")
        grade: VisionGrade = grade_image(front, back)
        return vision_to_dict(grade)
