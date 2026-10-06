from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from pokequant.api.app import create_app
from pokequant.api.deps import (
    get_catalog_service,
    get_forecast_service,
    get_price_service,
)
from pokequant.core.ids import uuid7
from pokequant.db.models import AssetClass, DailySnapshot, Instrument
from pokequant.domain.enums import Horizon, PriceKind
from pokequant.services.forecast_service import ForecastView

ASSET_CLASS = AssetClass(id=uuid7(), slug="pokemon", name="Pokemon TCG")


def make_instrument() -> Instrument:
    inst = Instrument(
        id=uuid7(),
        asset_class_id=ASSET_CLASS.id,
        symbol="PKM-X",
        name="Test Booster Box",
        release_date=date(2022, 1, 1),
        msrp_usd=Decimal("100.00"),
        currency="USD",
        is_active=True,
    )
    inst.asset_class = ASSET_CLASS
    inst.category = None
    return inst


def make_snapshots(instrument_id, n: int = 5) -> list[DailySnapshot]:
    return [
        DailySnapshot(
            instrument_id=instrument_id,
            snapshot_date=date(2024, 1, i + 1),
            price_usd=Decimal(f"{100 + i}.00"),
            price_source="synthetic",
            price_kind=PriceKind.INDEX,
            volume=3,
            active_listings=20,
            attention_index=55.0,
            is_synthetic=True,
        )
        for i in range(n)
    ]


class FakeCatalog:
    def __init__(self, instruments: list[Instrument]) -> None:
        self._by_id = {i.id: i for i in instruments}
        self._list = instruments

    def list_instruments(self, *, asset_class=None, limit=50, offset=0):
        return self._list[offset : offset + limit], len(self._list)

    def get(self, instrument_id):
        return self._by_id.get(instrument_id)


class FakePrice:
    def __init__(self, snaps: list[DailySnapshot]) -> None:
        self._snaps = snaps

    def history(self, instrument_id, *, start=None, end=None):
        return self._snaps

    def latest(self, instrument_id):
        return self._snaps[-1] if self._snaps else None


class FakeForecast:
    def __init__(self, view) -> None:
        self._view = view

    def get(self, instrument, horizon):
        return self._view


def build_client(*, catalog=None, price=None, forecast=None) -> TestClient:
    app = create_app()
    if catalog is not None:
        app.dependency_overrides[get_catalog_service] = lambda: catalog
    if price is not None:
        app.dependency_overrides[get_price_service] = lambda: price
    if forecast is not None:
        app.dependency_overrides[get_forecast_service] = lambda: forecast
    return TestClient(app)


def test_health() -> None:
    client = build_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_instruments() -> None:
    inst = make_instrument()
    client = build_client(catalog=FakeCatalog([inst]))
    resp = client.get("/api/v1/instruments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "PKM-X"
    assert body["items"][0]["asset_class"] == "pokemon"


def test_get_instrument_found_and_missing() -> None:
    inst = make_instrument()
    client = build_client(catalog=FakeCatalog([inst]))
    ok = client.get(f"/api/v1/instruments/{inst.id}")
    assert ok.status_code == 200
    assert ok.json()["name"] == "Test Booster Box"

    missing = client.get(f"/api/v1/instruments/{uuid7()}")
    assert missing.status_code == 404
    assert missing.json()["title"] == "not_found"


def test_prices() -> None:
    inst = make_instrument()
    snaps = make_snapshots(inst.id)
    client = build_client(catalog=FakeCatalog([inst]), price=FakePrice(snaps))
    resp = client.get(f"/api/v1/instruments/{inst.id}/prices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 5
    assert body["points"][0]["price_usd"] == 100.0
    assert body["points"][0]["is_synthetic"] is True


def test_forecast_stored() -> None:
    inst = make_instrument()
    view = ForecastView(
        instrument_id=inst.id,
        horizon=Horizon.D90,
        as_of=date(2024, 6, 30),
        last_price=200.0,
        predicted_price=230.0,
        predicted_return=0.1398,
        expected_change_pct=15.0,
        quantiles_price={"0.1": 210.0, "0.5": 230.0, "0.9": 260.0},
        quantiles_return={"0.1": 0.05, "0.5": 0.14, "0.9": 0.26},
        model_version="v20260101",
        is_synthetic=True,
        source="stored",
    )
    client = build_client(catalog=FakeCatalog([inst]), forecast=FakeForecast(view))
    resp = client.get(f"/api/v1/instruments/{inst.id}/forecast?horizon=d90")
    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_price"] == 230.0
    assert body["expected_change_pct"] == 15.0
    assert body["disclaimer"] is not None  # synthetic -> disclaimer present
    assert body["model_version"] == "v20260101"


def test_forecast_absent_returns_404() -> None:
    inst = make_instrument()
    client = build_client(catalog=FakeCatalog([inst]), forecast=FakeForecast(None))
    resp = client.get(f"/api/v1/instruments/{inst.id}/forecast")
    assert resp.status_code == 404


def test_card_search_endpoint() -> None:
    from pokequant.api.deps import get_grading_service
    from pokequant.grading.cards import CardRecord

    class FakeGrading:
        def search(self, query: str, *, page_size: int = 12):
            return [
                CardRecord(
                    id="sv3-1",
                    name="Charmander",
                    set_name="Obsidian Flames",
                    set_id="sv3",
                    number="1",
                    rarity="Common",
                    artist=None,
                    image_small=None,
                    image_large=None,
                    tcgplayer_url=None,
                    raw_usd=0.35,
                    raw_finish="normal",
                    raw_low=0.2,
                    raw_mid=0.4,
                    raw_high=0.8,
                    prices_updated_at=None,
                )
            ]

    app = create_app()
    app.dependency_overrides[get_grading_service] = lambda: FakeGrading()
    client = TestClient(app)
    resp = client.get("/api/v1/cards/search?q=charmander")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["name"] == "Charmander"
