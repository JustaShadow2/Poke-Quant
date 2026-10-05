from __future__ import annotations

from datetime import date

import pandas as pd

from pokequant.synthetic.generator import SyntheticParams, generate, seed_from_symbol


def test_generate_shape_and_columns() -> None:
    params = SyntheticParams(release_date=date(2022, 1, 1), msrp_usd=120.0)
    df = generate(params, end=date(2024, 1, 1), seed=1)
    assert list(df.columns) == ["price_usd", "volume", "active_listings", "attention_index"]
    assert len(df) == (date(2024, 1, 1) - date(2022, 1, 1)).days + 1
    assert isinstance(df.index, pd.DatetimeIndex)


def test_prices_are_positive() -> None:
    params = SyntheticParams(release_date=date(2022, 1, 1), msrp_usd=50.0)
    df = generate(params, end=date(2025, 1, 1), seed=7)
    assert (df["price_usd"] > 0).all()


def test_deterministic_given_seed() -> None:
    params = SyntheticParams(release_date=date(2022, 1, 1), msrp_usd=100.0)
    a = generate(params, end=date(2024, 1, 1), seed=42)
    b = generate(params, end=date(2024, 1, 1), seed=42)
    assert a.equals(b)


def test_different_seeds_differ() -> None:
    params = SyntheticParams(release_date=date(2022, 1, 1), msrp_usd=100.0)
    a = generate(params, end=date(2024, 1, 1), seed=1)
    b = generate(params, end=date(2024, 1, 1), seed=2)
    assert not a["price_usd"].equals(b["price_usd"])


def test_out_of_print_appreciation() -> None:
    # A chase set should, on average, appreciate well beyond MSRP long after OOP.
    params = SyntheticParams(
        release_date=date(2020, 1, 1), msrp_usd=100.0, hype=1.5, long_run_multiple=3.0
    )
    df = generate(params, end=date(2024, 12, 31), seed=seed_from_symbol("CHASE"))
    assert df["price_usd"].iloc[-30:].mean() > 1.6 * 100.0


def test_supply_declines_over_lifecycle() -> None:
    params = SyntheticParams(release_date=date(2021, 1, 1), msrp_usd=100.0)
    df = generate(params, end=date(2024, 1, 1), seed=3)
    assert df["active_listings"].iloc[:30].mean() > df["active_listings"].iloc[-30:].mean()


def test_empty_when_end_before_release() -> None:
    params = SyntheticParams(release_date=date(2025, 1, 1), msrp_usd=100.0)
    df = generate(params, end=date(2024, 1, 1), seed=1)
    assert df.empty


def test_seed_from_symbol_stable() -> None:
    assert seed_from_symbol("PKM-SV01-BB") == seed_from_symbol("PKM-SV01-BB")
    assert seed_from_symbol("A") != seed_from_symbol("B")
