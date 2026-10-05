from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from pokequant.features import technical as ta
from pokequant.features.builder import FEATURE_NAMES, build_features
from pokequant.ml.dataset import (
    build_dataset,
    forward_log_return,
    latest_feature_row,
    snapshots_to_frame,
)


def test_rsi_bounds(price_history: pd.DataFrame) -> None:
    rsi = ta.rsi(price_history["price_usd"], 14).dropna()
    assert (rsi >= 0).all() and (rsi <= 100).all()


def test_sma_is_causal(price_history: pd.DataFrame) -> None:
    price = price_history["price_usd"]
    full = ta.sma(price, 20)
    # SMA at an interior point must not change if we drop future data.
    cut = 200
    partial = ta.sma(price.iloc[: cut + 1], 20)
    assert np.isclose(full.iloc[cut], partial.iloc[cut])


def test_build_features_columns(price_history: pd.DataFrame) -> None:
    feats = build_features(price_history, date(2021, 1, 1))
    assert list(feats.columns) == FEATURE_NAMES
    assert len(feats) == len(price_history)


def test_features_no_lookahead(price_history: pd.DataFrame) -> None:
    release = date(2021, 1, 1)
    full = build_features(price_history, release)
    truncated = build_features(price_history.iloc[:300], release)
    # Feature values at t=250 must be identical whether or not future rows exist.
    row_full = full.iloc[250]
    row_trunc = truncated.iloc[250]
    pd.testing.assert_series_equal(row_full, row_trunc)


def test_forward_log_return_alignment() -> None:
    price = pd.Series(
        [100.0, 110.0, 121.0],
        index=pd.DatetimeIndex([date(2022, 1, 1), date(2022, 1, 2), date(2022, 1, 3)]),
    )
    y = forward_log_return(price, 1)
    assert np.isclose(y.iloc[0], np.log(110.0 / 100.0))
    assert np.isnan(y.iloc[-1])  # no future price for the last row


def test_build_dataset_no_target_leakage(
    multi_history: tuple[dict, dict],
) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, horizon_days=90)
    assert len(ds) > 0
    assert list(ds.X.columns) == FEATURE_NAMES
    # target present and finite
    assert np.isfinite(ds.y.to_numpy()).all()
    # last horizon days per instrument dropped (no future price) -> as_of never within
    # 90 days of each instrument's last date.
    for sym, df in histories.items():
        last = df.index.max()
        sym_as_of = ds.as_of[ds.instrument_id == sym]
        assert (sym_as_of <= last - pd.Timedelta(days=90)).all()


def test_latest_feature_row(price_history: pd.DataFrame) -> None:
    result = latest_feature_row(price_history, date(2021, 1, 1))
    assert result is not None
    x_row, last_price, as_of = result
    assert x_row.shape == (1, len(FEATURE_NAMES))
    assert last_price > 0
    assert as_of == price_history.index[-1].date()


def test_snapshots_to_frame_roundtrip() -> None:
    class Row:
        def __init__(self, d, p):
            self.snapshot_date = d
            self.price_usd = p
            self.volume = 5
            self.active_listings = 10
            self.attention_index = 50.0

    rows = [Row(date(2022, 1, 2), 100.0), Row(date(2022, 1, 1), 99.0)]
    df = snapshots_to_frame(rows)
    assert list(df.index) == [pd.Timestamp(2022, 1, 1), pd.Timestamp(2022, 1, 2)]  # sorted
    assert df["price_usd"].tolist() == [99.0, 100.0]
