from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import pandas as pd
import pytest

from pokequant.synthetic.generator import SyntheticParams, generate, seed_from_symbol


@pytest.fixture
def price_history() -> pd.DataFrame:
    """A single deterministic synthetic price history."""
    params = SyntheticParams(release_date=date(2021, 1, 1), msrp_usd=100.0)
    return generate(params, end=date(2024, 6, 30), seed=seed_from_symbol("TEST-A"))


@pytest.fixture
def multi_history() -> tuple[dict[str, pd.DataFrame], dict[str, date]]:
    """Several instruments for dataset/training tests."""
    histories: dict[str, pd.DataFrame] = {}
    releases: dict[str, date] = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E", "F"]):
        params = SyntheticParams(
            release_date=date(2021, 1, 1), msrp_usd=90.0 + 15 * i, hype=1.0 + 0.1 * i
        )
        histories[sym] = generate(params, end=date(2024, 6, 30), seed=seed_from_symbol(sym))
        releases[sym] = params.release_date
    return histories, releases
