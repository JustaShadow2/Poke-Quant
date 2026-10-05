"""Inference: turn a trained forecaster + price history into a forecast.

Point/interval forecasts are produced in *return* space and mapped back to price
via ``price = last_price * exp(return)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np

from pokequant.domain.enums import Horizon
from pokequant.ml.dataset import latest_feature_row


@dataclass
class ForecastResult:
    instrument_id: str
    as_of: date
    horizon: Horizon
    last_price: float
    predicted_return: float
    predicted_price: float
    quantiles_return: dict[float, float]
    quantiles_price: dict[float, float]
    model_kind: str

    @property
    def expected_change_pct(self) -> float:
        return (self.predicted_price / self.last_price - 1.0) * 100.0


def forecast_instrument(
    model: object,
    instrument_id: str,
    price_df: object,  # pandas DataFrame (typed loosely to avoid import cost here)
    release_date: date,
    horizon: Horizon,
    *,
    quantiles: Sequence[float] = (0.1, 0.5, 0.9),
    model_kind: str = "gbm",
) -> Optional[ForecastResult]:
    """Produce a forecast for one instrument, or None if history is insufficient."""
    prepared = latest_feature_row(price_df, release_date)
    if prepared is None:
        return None
    x_row, last_price, as_of = prepared

    predicted_return = float(model.predict_return(x_row)[0])  # type: ignore[attr-defined]
    q_ret = model.predict_quantiles(x_row, quantiles)  # type: ignore[attr-defined]
    quantiles_return = {q: float(v[0]) for q, v in q_ret.items()}
    quantiles_price = {q: float(last_price * np.exp(r)) for q, r in quantiles_return.items()}

    return ForecastResult(
        instrument_id=instrument_id,
        as_of=as_of,
        horizon=horizon,
        last_price=last_price,
        predicted_return=predicted_return,
        predicted_price=float(last_price * np.exp(predicted_return)),
        quantiles_return=quantiles_return,
        quantiles_price=quantiles_price,
        model_kind=model_kind,
    )
