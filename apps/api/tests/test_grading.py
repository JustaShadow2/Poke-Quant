from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from pokequant.grading.cards import parse_card, parse_cards, pick_raw_price
from pokequant.grading.prices import estimate_graded_prices
from pokequant.grading.roi import compute_roi, probs_from_predicted_grade
from pokequant.grading.vision import grade_image


def test_pick_raw_prefers_holofoil_market() -> None:
    prices = {
        "normal": {"market": 1.0, "mid": 1.2},
        "holofoil": {"market": 14.5, "low": 10.0, "mid": 15.0, "high": 22.0},
    }
    market, finish, band = pick_raw_price(prices)
    assert market == 14.5
    assert finish == "holofoil"
    assert band["low"] == 10.0


def test_parse_cards_skips_missing_prices() -> None:
    payload = {
        "data": [
            {
                "id": "sv3-199",
                "name": "Charizard ex",
                "number": "199",
                "rarity": "Special Illustration Rare",
                "set": {"id": "sv3", "name": "Obsidian Flames"},
                "images": {"small": "http://example/s.png", "large": "http://example/l.png"},
                "tcgplayer": {
                    "url": "http://tcgplayer/x",
                    "updatedAt": "2026/01/01",
                    "prices": {"holofoil": {"market": 88.0, "mid": 90.0}},
                },
            }
        ]
    }
    cards = parse_cards(payload)
    assert len(cards) == 1
    assert cards[0].raw_usd == 88.0
    assert cards[0].set_name == "Obsidian Flames"


def test_parse_card_without_tcgplayer() -> None:
    card = parse_card({"id": "x", "name": "Pikachu", "number": "1", "set": {"name": "Base"}})
    assert card.raw_usd is None
    assert card.name == "Pikachu"


def test_graded_estimates_are_above_raw() -> None:
    graded = estimate_graded_prices(50.0, "Illustration Rare")
    assert graded["psa10_usd"] > graded["psa9_usd"] > graded["psa8_usd"]
    assert graded["psa9_usd"] > 50.0


def test_expensive_cards_have_compressed_psa10_multiple() -> None:
    cheap = estimate_graded_prices(0.5, "Common")
    expensive = estimate_graded_prices(400.0, "Common")
    cheap_mult = cheap["psa10_usd"] / 0.5
    expensive_mult = expensive["psa10_usd"] / 400.0
    assert cheap_mult > expensive_mult


def test_roi_sell_raw_when_premium_too_small() -> None:
    roi = compute_roi(raw_usd=100.0, psa9_usd=105.0, psa10_usd=120.0, psa8_usd=95.0)
    assert roi.verdict in {"sell_raw", "lean_raw"}
    assert roi.expected_net_vs_raw < 0


def test_roi_grade_when_psa10_is_huge() -> None:
    roi = compute_roi(raw_usd=20.0, psa9_usd=40.0, psa10_usd=250.0, psa8_usd=18.0)
    assert roi.expected_net_vs_raw > 0
    assert roi.verdict in {"grade", "borderline"}


def test_vision_shifts_probabilities_up() -> None:
    prior = probs_from_predicted_grade(None)
    ten = probs_from_predicted_grade(9.8)
    eight = probs_from_predicted_grade(8.0)
    assert ten[0] > prior[0]
    assert eight[0] < prior[0]


def _fake_card_png() -> bytes:
    """A synthetic 'card': yellow border, darker artwork, mild corner whitening."""
    img = Image.new("RGB", (400, 560), (240, 210, 40))
    arr = np.array(img)
    arr[40:520, 36:364] = (40, 70, 130)
    # White nicks on two corners.
    arr[:12, :12] = 255
    arr[-12:, -12:] = 255
    out = BytesIO()
    Image.fromarray(arr).save(out, format="PNG")
    return out.getvalue()


def test_vision_grade_returns_subscores() -> None:
    result = grade_image(_fake_card_png())
    assert 6.0 <= result.predicted_grade <= 10.0
    assert result.centering.score >= 6.0
    assert result.corners.name == "corners"
    assert "not a psa grade" in result.disclaimer.lower()
