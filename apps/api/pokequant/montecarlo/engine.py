"""Monte Carlo GBM price path simulation.

Simulates N future price paths using Geometric Brownian Motion calibrated to the
model's forecast return and historical volatility. Produces probability distributions
for target returns and price levels at the forecast horizon.

Usage:
    result = simulate(last_price=100, expected_return=0.12, volatility=0.25,
                      horizon_days=90, n_paths=10000)
    print(result.prob_above(125))  # P(price > 125 at horizon)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class MonteCarloResult:
    """Results from a Monte Carlo simulation."""

    last_price: float
    horizon_days: int
    n_paths: int
    expected_return: float
    volatility: float

    # Distribution statistics at horizon.
    mean_price: float = 0.0
    median_price: float = 0.0
    std_price: float = 0.0
    percentiles: dict[int, float] = field(default_factory=dict)
    # {5: p5, 10: p10, 25: p25, 50: median, 75: p75, 90: p90, 95: p95}

    # Probability metrics.
    prob_positive: float = 0.0  # P(return > 0)
    prob_loss_10: float = 0.0  # P(return < -10%)
    prob_gain_25: float = 0.0  # P(return > 25%)
    prob_gain_50: float = 0.0  # P(return > 50%)
    prob_double: float = 0.0  # P(return > 100%)

    # Target return probabilities (user-specified).
    target_probs: dict[str, float] = field(default_factory=dict)

    def prob_above(self, target_price: float) -> float:
        """Probability final price exceeds target (computed from stored paths)."""
        return self.target_probs.get(f"above_{target_price:.2f}", 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_price": round(self.last_price, 2),
            "horizon_days": self.horizon_days,
            "n_paths": self.n_paths,
            "expected_return": round(self.expected_return, 4),
            "volatility": round(self.volatility, 4),
            "mean_price": round(self.mean_price, 2),
            "median_price": round(self.median_price, 2),
            "std_price": round(self.std_price, 2),
            "percentiles": {str(k): round(v, 2) for k, v in self.percentiles.items()},
            "prob_positive": round(self.prob_positive, 4),
            "prob_loss_10": round(self.prob_loss_10, 4),
            "prob_gain_25": round(self.prob_gain_25, 4),
            "prob_gain_50": round(self.prob_gain_50, 4),
            "prob_double": round(self.prob_double, 4),
            "target_probs": {k: round(v, 4) for k, v in self.target_probs.items()},
        }


def simulate(
    last_price: float,
    expected_return: float,
    volatility: float,
    horizon_days: int = 90,
    n_paths: int = 10000,
    target_prices: list[float] | None = None,
    seed: int | None = 42,
) -> MonteCarloResult:
    """Run Monte Carlo GBM simulation.

    Args:
        last_price: Current price.
        expected_return: Expected log-return over the horizon (from model forecast).
        volatility: Annualized volatility (from realized vol feature).
        horizon_days: Number of days to simulate.
        n_paths: Number of simulation paths.
        target_prices: Specific price levels to compute P(price > target).
        seed: Random seed for reproducibility.

    Returns:
        MonteCarloResult with distribution statistics and probabilities.
    """
    rng = np.random.default_rng(seed)

    # Convert to daily parameters.
    dt = 1.0 / 365.0  # daily step in years
    # Drift: annualized drift from expected log-return.
    annual_return = expected_return * (365.0 / horizon_days)
    mu = annual_return - 0.5 * volatility**2  # risk-neutral drift adjustment
    sigma = volatility

    # Generate paths.
    steps = horizon_days
    # Random shocks: (n_paths, steps)
    z = rng.standard_normal((n_paths, steps))
    # Daily log-returns.
    daily_log_ret = mu * dt + sigma * np.sqrt(dt) * z
    # Cumulative log-returns.
    cum_log_ret = daily_log_ret.cumsum(axis=1)
    # Final prices.
    final_prices = last_price * np.exp(cum_log_ret[:, -1])

    # Statistics.
    mean_p = float(np.mean(final_prices))
    median_p = float(np.median(final_prices))
    std_p = float(np.std(final_prices))

    pct_keys = [5, 10, 25, 50, 75, 90, 95]
    percentiles = {k: float(np.percentile(final_prices, k)) for k in pct_keys}

    # Return-based probabilities.
    returns = final_prices / last_price - 1
    prob_pos = float((returns > 0).mean())
    prob_loss_10 = float((returns < -0.10).mean())
    prob_gain_25 = float((returns > 0.25).mean())
    prob_gain_50 = float((returns > 0.50).mean())
    prob_double = float((returns > 1.0).mean())

    # Target price probabilities.
    target_probs: dict[str, float] = {}
    for tp in (target_prices or []):
        key = f"above_{tp:.2f}"
        target_probs[key] = float((final_prices > tp).mean())

    return MonteCarloResult(
        last_price=last_price,
        horizon_days=horizon_days,
        n_paths=n_paths,
        expected_return=expected_return,
        volatility=volatility,
        mean_price=mean_p,
        median_price=median_p,
        std_price=std_p,
        percentiles=percentiles,
        prob_positive=prob_pos,
        prob_loss_10=prob_loss_10,
        prob_gain_25=prob_gain_25,
        prob_gain_50=prob_gain_50,
        prob_double=prob_double,
        target_probs=target_probs,
    )
