"""Technical indicators.

All functions are *causal*: value at time t depends only on data up to t. This is
the single most important leakage guard for time-series features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(price: pd.Series) -> pd.Series:
    return np.log(price).diff()


def trailing_log_return(price: pd.Series, window: int) -> pd.Series:
    """Log return over the trailing `window` days: log(P_t / P_{t-window})."""
    return np.log(price).diff(window)


def sma(price: pd.Series, window: int) -> pd.Series:
    return price.rolling(window, min_periods=window).mean()


def ema(price: pd.Series, span: int) -> pd.Series:
    return price.ewm(span=span, adjust=False).mean()


def sma_ratio(price: pd.Series, window: int) -> pd.Series:
    """Relative distance of price above/below its SMA (0 == on the average)."""
    return price / sma(price, window) - 1.0


def ema_ratio(price: pd.Series, span: int) -> pd.Series:
    return price / ema(price, span) - 1.0


def rsi(price: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index in [0, 100]."""
    delta = price.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # When there are no losses over the window RSI saturates at 100.
    return out.where(avg_loss != 0.0, 100.0)


def macd_hist(price: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD histogram = MACD line - signal line, normalized by price."""
    macd_line = ema(price, fast) - ema(price, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return (macd_line - signal_line) / price


def bollinger_pctb(price: pd.Series, window: int = 20, k: float = 2.0) -> pd.Series:
    """%B: position within the Bollinger band (0 = lower, 1 = upper)."""
    mid = sma(price, window)
    std = price.rolling(window, min_periods=window).std(ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    span = (upper - lower).replace(0.0, np.nan)
    return (price - lower) / span


def bollinger_width(price: pd.Series, window: int = 20, k: float = 2.0) -> pd.Series:
    """Band width relative to the middle band - a volatility proxy."""
    mid = sma(price, window)
    std = price.rolling(window, min_periods=window).std(ddof=0)
    return (2.0 * k * std) / mid


def realized_vol(price: pd.Series, window: int) -> pd.Series:
    """Rolling std of daily log returns (not annualized)."""
    return log_returns(price).rolling(window, min_periods=max(2, window // 2)).std(ddof=0)


def max_drawdown(price: pd.Series, window: int) -> pd.Series:
    """Worst peak-to-current drawdown within a trailing window (<= 0)."""
    roll_max = price.rolling(window, min_periods=1).max()
    return price / roll_max - 1.0
