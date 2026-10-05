from __future__ import annotations

from datetime import date, datetime, timezone

from pokequant.domain.enums import Condition, PriceKind
from pokequant.ingestion.consolidation import PriceCandidate, pick_price
from pokequant.providers.ebay_browse import parse_search
from pokequant.providers.fred import parse_observations
from pokequant.providers.pokemontcg import parse_sets
from pokequant.providers.ratelimit import TokenBucket


# --------------------------------------------------------------------- ratelimit
class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_token_bucket_allows_burst_then_paces() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate_per_sec=2.0, capacity=2.0, time_fn=clock.time, sleep_fn=clock.sleep)
    assert bucket.acquire() == 0.0  # token 1 (burst)
    assert bucket.acquire() == 0.0  # token 2 (burst)
    waited = bucket.acquire()  # must wait ~0.5s for a refill at 2/s
    assert abs(waited - 0.5) < 1e-9


def test_token_bucket_refills_over_time() -> None:
    clock = FakeClock()
    bucket = TokenBucket(2.0, 2.0, time_fn=clock.time, sleep_fn=clock.sleep)
    bucket.acquire()
    bucket.acquire()
    clock.now += 1.0  # 1 second -> 2 tokens refilled
    assert bucket.acquire() == 0.0


# --------------------------------------------------------------------- pokemontcg
def test_parse_sets() -> None:
    payload = {
        "data": [
            {
                "id": "sv1",
                "name": "Scarlet & Violet",
                "series": "SV",
                "releaseDate": "2023/03/31",
                "total": 258,
            },
            {
                "id": "cel25",
                "name": "Celebrations",
                "series": "SWSH",
                "releaseDate": "2021/10/08",
                "total": 25,
            },
            {"id": "bad", "name": "No Date", "series": "X"},
        ]
    }
    sets = parse_sets(payload)
    assert len(sets) == 3
    assert sets[0].set_id == "sv1"
    assert sets[0].release_date == date(2023, 3, 31)
    assert sets[2].release_date is None


# --------------------------------------------------------------------- ebay
def test_parse_search_median_and_supply() -> None:
    payload = {
        "total": 128,
        "itemSummaries": [
            {"price": {"value": "100.00", "currency": "USD"}},
            {"price": {"value": "120.00", "currency": "USD"}},
            {"price": {"value": "140.00", "currency": "USD"}},
            {"price": {"value": "9999.00", "currency": "EUR"}},  # non-USD dropped
        ],
    }
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price, supply = parse_search(payload, observed_at=now)
    assert price is not None
    assert price.price_usd == 120.0  # median of 100/120/140
    assert price.kind == PriceKind.LISTING
    assert price.condition == Condition.SEALED
    assert supply is not None
    assert supply.active_listings == 128


def test_parse_search_empty() -> None:
    price, supply = parse_search({"itemSummaries": []}, observed_at=datetime.now(timezone.utc))
    assert price is None
    assert supply is None


# --------------------------------------------------------------------- fred
def test_parse_observations_skips_missing() -> None:
    payload = {
        "observations": [
            {"date": "2024-01-01", "value": "5.33"},
            {"date": "2024-01-02", "value": "."},  # FRED missing marker
            {"date": "2024-01-03", "value": "5.31"},
        ]
    }
    points = parse_observations(payload, "DFF")
    assert len(points) == 2
    assert points[0].series_id == "DFF"
    assert points[0].value == 5.33


# --------------------------------------------------------------------- consolidation
def test_pick_price_prefers_sale_over_listing() -> None:
    candidates = [
        PriceCandidate(100.0, "ebay", PriceKind.LISTING, tier=2),
        PriceCandidate(95.0, "pricecharting", PriceKind.MARKET, tier=1),
        PriceCandidate(98.0, "auctions", PriceKind.SALE, tier=1),
    ]
    best = pick_price(candidates)
    assert best.kind == PriceKind.SALE


def test_pick_price_breaks_ties_by_tier() -> None:
    candidates = [
        PriceCandidate(100.0, "b", PriceKind.MARKET, tier=3),
        PriceCandidate(101.0, "a", PriceKind.MARKET, tier=1),
    ]
    assert pick_price(candidates).source == "a"
