"""Generative model for realistic sealed-product price/supply/attention history.

The model encodes the stylized facts of sealed collectibles (docs/02-data-sources.md,
docs/04-feature-engineering.md):

* Price hugs MSRP while a product is *in print* (retail competition caps upside).
* After the product goes *out of print* (OOP), scarcity drives a multi-year
  appreciation toward a long-run premium multiple.
* Strong Q4 (holiday) seasonality.
* Autocorrelated transient deviations (AR(1)) - momentum, not white noise.
* Occasional discrete shocks: reprints (negative, persistent) and hype (positive).
* Supply (active listings) is high near release and dries up over the lifecycle;
  attention (search-like index) tracks recent momentum.

Everything is deterministic given a seed, which is essential for reproducible
tests and stable dev datasets.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

_DAYS_PER_MONTH = 30.4375
_DEC_PEAK_DOY = 335  # ~Dec 1: center of the holiday bump


@dataclass(frozen=True)
class SyntheticParams:
    """Calibration knobs for one instrument's synthetic trajectory."""

    release_date: date
    msrp_usd: float
    out_of_print_months: float = 14.0
    in_print_discount: float = 0.95  # sealed often sits just below MSRP at retail
    long_run_multiple: float = 2.3  # eventual sealed premium vs MSRP
    annual_drift: float = 0.05  # secular drift on top of the lifecycle curve
    volatility: float = 0.018  # daily log-vol of AR(1) innovations
    ar1: float = 0.93  # persistence of transient deviations
    seasonal_amp: float = 0.06  # amplitude (log) of the Q4 bump
    hype: float = 1.0  # scales premium & volatility (chase-set intensity)
    reprint_prob_annual: float = 0.06  # annualized probability of a reprint shock

    def with_hype(self, hype: float) -> SyntheticParams:
        return SyntheticParams(
            release_date=self.release_date,
            msrp_usd=self.msrp_usd,
            out_of_print_months=self.out_of_print_months,
            in_print_discount=self.in_print_discount,
            long_run_multiple=self.long_run_multiple + 0.6 * (hype - 1.0),
            annual_drift=self.annual_drift,
            volatility=self.volatility * (0.8 + 0.4 * hype),
            ar1=self.ar1,
            seasonal_amp=self.seasonal_amp,
            hype=hype,
            reprint_prob_annual=self.reprint_prob_annual,
        )


def seed_from_symbol(symbol: str) -> int:
    """Stable 32-bit seed derived from an instrument symbol."""
    digest = hashlib.sha256(symbol.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _lifecycle_multiple(days_since_release: np.ndarray, params: SyntheticParams) -> np.ndarray:
    """Premium-over-MSRP multiple as a function of lifecycle age (vectorized)."""
    oop_days = params.out_of_print_months * _DAYS_PER_MONTH
    # Logistic ramp centered a little after OOP; ~1 year to mostly complete.
    scale = max(oop_days * 0.45, 45.0)
    ramp = 1.0 / (1.0 + np.exp(-(days_since_release - oop_days) / scale))
    base = params.in_print_discount + (params.long_run_multiple - params.in_print_discount) * ramp
    drift = np.exp(params.annual_drift * np.maximum(days_since_release, 0) / 365.0)
    return base * drift


def generate(
    params: SyntheticParams,
    *,
    end: date,
    start: date | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Generate a daily synthetic series.

    Returns a DataFrame indexed by normalized daily Timestamp with columns:
    ``price_usd``, ``volume``, ``active_listings``, ``attention_index``.
    History starts at the later of ``start`` and the product's release date.
    """
    hist_start = params.release_date if start is None else max(start, params.release_date)
    if end < hist_start:
        return pd.DataFrame(columns=["price_usd", "volume", "active_listings", "attention_index"])

    n = (end - hist_start).days + 1
    dates = [hist_start + timedelta(days=i) for i in range(n)]
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    rng = np.random.default_rng(seed)

    days_since_release = np.array([(d - params.release_date).days for d in dates], dtype=float)
    doy = np.array([d.timetuple().tm_yday for d in dates], dtype=float)

    mean_log = np.log(params.msrp_usd) + np.log(_lifecycle_multiple(days_since_release, params))
    seasonal = params.seasonal_amp * np.cos(2.0 * np.pi * (doy - _DEC_PEAK_DOY) / 365.0)

    # AR(1) transient deviations + persistent-but-decaying shock state.
    innovations = rng.normal(0.0, params.volatility, size=n)
    daily_reprint_p = params.reprint_prob_annual / 365.0
    transient = np.zeros(n)
    shock = np.zeros(n)
    e = 0.0
    s = 0.0
    for t in range(n):
        e = params.ar1 * e + innovations[t]
        s *= 0.992  # shocks decay over ~4 months
        if days_since_release[t] > 0:
            u = rng.random()
            if u < daily_reprint_p:
                s += -0.22  # reprint: ~-20% persistent level shift
            elif u > 1.0 - daily_reprint_p * 0.6 * params.hype:
                s += 0.15 * params.hype  # hype spike
        transient[t] = e
        shock[t] = s

    log_price = mean_log + seasonal + transient + shock
    price = np.round(np.exp(log_price), 2)

    # Supply: high near release, decays over the lifecycle; jitter for realism.
    oop_days = params.out_of_print_months * _DAYS_PER_MONTH
    base_supply = 400.0 * np.exp(-np.maximum(days_since_release, 0) / (oop_days * 1.5))
    active = (
        np.maximum(3.0, base_supply * (1.0 + rng.normal(0.0, 0.15, size=n))).round().astype(int)
    )

    # Volume loosely tracks supply availability; also jittered.
    volume = np.maximum(
        0, (base_supply * 0.08 * (1.0 + rng.normal(0.0, 0.3, size=n))).round()
    ).astype(int)

    # Attention index: momentum-driven (recent log returns), 0-100-ish, smoothed.
    log_ret = np.diff(log_price, prepend=log_price[0])
    momentum = pd.Series(log_ret).rolling(14, min_periods=1).mean().to_numpy()
    attention = 50.0 + 800.0 * momentum + rng.normal(0.0, 3.0, size=n)
    attention = np.clip(attention, 0.0, 100.0)

    return pd.DataFrame(
        {
            "price_usd": price,
            "volume": volume,
            "active_listings": active,
            "attention_index": np.round(attention, 2),
        },
        index=idx,
    )
