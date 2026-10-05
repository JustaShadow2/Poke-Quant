"""Assemble a point-in-time feature matrix for a single instrument.

Input: a daily DataFrame indexed by Timestamp with a required ``price_usd`` column
and optional ``volume`` / ``active_listings`` / ``attention_index`` columns.
Output: a DataFrame of the Phase-1 feature set indexed by the same dates.

Missing optional inputs yield NaN features on purpose - the gradient-boosting
models handle NaNs natively, and the naive baseline only needs price.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from pokequant.features import technical as ta

FEATURE_SET = "phase1.v1"

FEATURE_NAMES: list[str] = [
    # price / technical
    "log_price",
    "ret_7",
    "ret_30",
    "ret_90",
    "mom_accel",
    "sma_ratio_20",
    "sma_ratio_50",
    "ema_ratio_20",
    "rsi_14",
    "macd_hist",
    "bb_pctb_20",
    "bb_width_20",
    "vol_30",
    "vol_90",
    "max_dd_180",
    # supply / liquidity / demand
    "log_active_listings",
    "listings_chg_30",
    "log_volume_30",
    "attention_index",
    "attention_chg_30",
    # lifecycle / calendar
    "days_since_release",
    "months_since_release",
    "month_sin",
    "month_cos",
    "is_q4",
]


def _optional(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].astype(float)
    return pd.Series(np.nan, index=df.index, dtype=float)


def build_features(df: pd.DataFrame, release_date: date) -> pd.DataFrame:
    """Compute the Phase-1 feature matrix. `df` must be sorted ascending by date."""
    if df.empty:
        return pd.DataFrame(columns=FEATURE_NAMES)

    df = df.sort_index()
    price = df["price_usd"].astype(float)
    active = _optional(df, "active_listings")
    volume = _optional(df, "volume")
    attention = _optional(df, "attention_index")

    idx = df.index
    months = np.array([ts.month for ts in idx], dtype=float)
    days_since = np.array([(ts.date() - release_date).days for ts in idx], dtype=float)

    feats = pd.DataFrame(index=idx)
    feats["log_price"] = np.log(price)
    feats["ret_7"] = ta.trailing_log_return(price, 7)
    feats["ret_30"] = ta.trailing_log_return(price, 30)
    feats["ret_90"] = ta.trailing_log_return(price, 90)
    feats["mom_accel"] = feats["ret_30"] / 30.0 - feats["ret_90"] / 90.0
    feats["sma_ratio_20"] = ta.sma_ratio(price, 20)
    feats["sma_ratio_50"] = ta.sma_ratio(price, 50)
    feats["ema_ratio_20"] = ta.ema_ratio(price, 20)
    feats["rsi_14"] = ta.rsi(price, 14)
    feats["macd_hist"] = ta.macd_hist(price)
    feats["bb_pctb_20"] = ta.bollinger_pctb(price, 20)
    feats["bb_width_20"] = ta.bollinger_width(price, 20)
    feats["vol_30"] = ta.realized_vol(price, 30)
    feats["vol_90"] = ta.realized_vol(price, 90)
    feats["max_dd_180"] = ta.max_drawdown(price, 180)

    feats["log_active_listings"] = np.log1p(active)
    feats["listings_chg_30"] = active.pct_change(30, fill_method=None)
    feats["log_volume_30"] = np.log1p(volume.rolling(30, min_periods=5).mean())
    feats["attention_index"] = attention
    feats["attention_chg_30"] = attention.diff(30)

    feats["days_since_release"] = days_since
    feats["months_since_release"] = days_since / 30.4375
    feats["month_sin"] = np.sin(2.0 * np.pi * months / 12.0)
    feats["month_cos"] = np.cos(2.0 * np.pi * months / 12.0)
    feats["is_q4"] = np.isin(months, [10.0, 11.0, 12.0]).astype(float)

    return feats[FEATURE_NAMES]
