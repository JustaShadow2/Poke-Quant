"""Turn per-instrument price history into a supervised learning table.

Target = forward log-return over the horizon: ``y_t = log(P_{t+h} / P_t)``.
Predicting *returns* (not price levels) keeps the target stationary and
comparable across instruments of very different price scales.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import numpy as np
import pandas as pd

from pokequant.features.builder import FEATURE_NAMES, build_features

# Internal (double-underscore) columns never collide with feature names.
_Y = "__y"
_LAST_PRICE = "__last_price"
_INSTRUMENT = "__instrument_id"
_AS_OF = "__as_of"


@dataclass
class SupervisedDataset:
    """A leakage-safe supervised dataset with alignment metadata."""

    X: pd.DataFrame  # feature matrix (columns == FEATURE_NAMES)
    y: pd.Series  # forward log-return target
    as_of: pd.Series  # as-of date per row (datetime64)
    instrument_id: pd.Series  # instrument id per row
    last_price: pd.Series  # price at as-of (for reconstructing price forecasts)
    horizon_days: int

    def __len__(self) -> int:
        return len(self.X)


def snapshots_to_frame(records: Iterable[Any]) -> pd.DataFrame:
    """Convert daily-snapshot rows into the price DataFrame the ML stack expects.

    `records` is any iterable of objects exposing ``snapshot_date``, ``price_usd``,
    ``volume``, ``active_listings`` and ``attention_index`` attributes.
    """
    cols = ["price_usd", "volume", "active_listings", "attention_index"]
    rows = list(records)
    if not rows:
        return pd.DataFrame(columns=cols)
    data: dict[str, list[object]] = {c: [] for c in cols}
    index: list[pd.Timestamp] = []
    for r in rows:
        index.append(pd.Timestamp(r.snapshot_date))
        data["price_usd"].append(float(r.price_usd))
        data["volume"].append(r.volume)
        data["active_listings"].append(r.active_listings)
        data["attention_index"].append(r.attention_index)
    return pd.DataFrame(data, index=pd.DatetimeIndex(index)).sort_index()


def forward_log_return(price: pd.Series, horizon_days: int) -> pd.Series:
    return np.log(price.shift(-horizon_days) / price)


def build_instrument_frame(
    price_df: pd.DataFrame,
    release_date: date,
    horizon_days: int,
    *,
    min_age_days: int = 30,
) -> pd.DataFrame:
    """Feature+target frame for one instrument (rows without a target dropped)."""
    feats = build_features(price_df, release_date)
    if feats.empty:
        return feats
    price = price_df["price_usd"].astype(float)
    frame = feats.copy()
    frame[_Y] = forward_log_return(price, horizon_days)
    frame[_LAST_PRICE] = price
    frame = frame[frame["days_since_release"] >= min_age_days]
    return frame.dropna(subset=[_Y, "log_price"])


def build_dataset(
    histories: dict[str, pd.DataFrame],
    release_dates: dict[str, date],
    horizon_days: int,
    *,
    min_age_days: int = 30,
) -> SupervisedDataset:
    """Assemble a multi-instrument supervised dataset.

    `histories` maps instrument_id -> daily price DataFrame; `release_dates`
    maps instrument_id -> release date.
    """
    parts: list[pd.DataFrame] = []
    for instrument_id, price_df in histories.items():
        release = release_dates.get(instrument_id)
        if release is None or price_df.empty:
            continue
        frame = build_instrument_frame(price_df, release, horizon_days, min_age_days=min_age_days)
        if frame.empty:
            continue
        frame = frame.copy()
        frame[_INSTRUMENT] = instrument_id
        frame[_AS_OF] = frame.index
        parts.append(frame)

    if not parts:
        empty = pd.DataFrame(columns=FEATURE_NAMES)
        return SupervisedDataset(
            X=empty,
            y=pd.Series(dtype=float),
            as_of=pd.Series(dtype="datetime64[ns]"),
            instrument_id=pd.Series(dtype=object),
            last_price=pd.Series(dtype=float),
            horizon_days=horizon_days,
        )

    full = pd.concat(parts, axis=0, ignore_index=True)
    return SupervisedDataset(
        X=full[FEATURE_NAMES].reset_index(drop=True),
        y=full[_Y].reset_index(drop=True),
        as_of=pd.to_datetime(full[_AS_OF]).reset_index(drop=True),
        instrument_id=full[_INSTRUMENT].reset_index(drop=True),
        last_price=full[_LAST_PRICE].reset_index(drop=True),
        horizon_days=horizon_days,
    )


def latest_feature_row(
    price_df: pd.DataFrame, release_date: date
) -> Optional[tuple[pd.DataFrame, float, date]]:
    """Feature row at the most recent available date (for inference).

    Returns (X_row_df, last_price, as_of_date) or None if there is no usable
    history.
    """
    feats = build_features(price_df, release_date)
    if feats.empty:
        return None
    row = feats.iloc[[-1]]
    if not np.isfinite(row["log_price"].iloc[0]):
        return None
    as_of = feats.index[-1].date()
    last_price = float(price_df["price_usd"].astype(float).iloc[-1])
    return row.reset_index(drop=True), last_price, as_of
