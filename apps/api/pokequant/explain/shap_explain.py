"""SHAP-based local and global explainability for GBM forecasts.

Uses TreeExplainer (exact Shapley values for tree models) to produce per-feature
attributions for each prediction. The output is an ordered list of feature
contributions that sum (approximately) to the predicted return minus the base value.

Design principles (from docs/08-explainable-ai.md):
- Every surfaced prediction has a stored, faithful explanation.
- Attributions are additive: base_value + sum(shap_values) ≈ prediction.
- Top features are surfaced; the full vector is stored for audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from pokequant.ml.gbm import GradientBoostingForecaster


@dataclass(frozen=True)
class FeatureAttribution:
    """A single feature's SHAP contribution to a prediction."""

    feature: str
    value: float  # the feature's actual value for this observation
    shap_value: float  # signed contribution to prediction
    abs_shap: float  # |contribution| for ranking

    @property
    def direction(self) -> str:
        if self.shap_value > 0.005:
            return "positive"
        if self.shap_value < -0.005:
            return "negative"
        return "neutral"


@dataclass
class Explanation:
    """Full explanation for one prediction."""

    instrument_id: str
    horizon: str
    predicted_return: float
    base_value: float
    attributions: list[FeatureAttribution] = field(default_factory=list)
    top_positive: list[FeatureAttribution] = field(default_factory=list)
    top_negative: list[FeatureAttribution] = field(default_factory=list)
    model_version: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "horizon": self.horizon,
            "predicted_return": round(self.predicted_return, 6),
            "base_value": round(self.base_value, 6),
            "top_positive": [
                {"feature": a.feature, "value": round(a.value, 4),
                 "shap_value": round(a.shap_value, 6), "direction": a.direction}
                for a in self.top_positive
            ],
            "top_negative": [
                {"feature": a.feature, "value": round(a.value, 4),
                 "shap_value": round(a.shap_value, 6), "direction": a.direction}
                for a in self.top_negative
            ],
            "num_features": len(self.attributions),
            "model_version": self.model_version,
        }


def _get_median_model(forecaster: GradientBoostingForecaster) -> Any:
    """Extract the median quantile model (the one closest to q=0.5)."""
    q = forecaster._median_q()
    return forecaster._models[q]


def explain_prediction(
    forecaster: GradientBoostingForecaster,
    X: pd.DataFrame,
    *,
    instrument_id: str = "",
    horizon: str = "",
    model_version: Optional[str] = None,
    top_k: int = 5,
) -> Explanation:
    """Compute SHAP attributions for a single prediction (one row of X).

    Args:
        forecaster: The trained GBM forecaster.
        X: Feature DataFrame (1 or more rows; first row is explained).
        instrument_id: For metadata.
        horizon: For metadata.
        model_version: For metadata.
        top_k: Number of top positive/negative features to surface.

    Returns:
        Explanation with ordered attributions.
    """
    import shap

    model = _get_median_model(forecaster)
    feature_names = forecaster.feature_names

    # TreeExplainer for exact SHAP values on tree-based models.
    explainer = shap.TreeExplainer(model)

    # Prepare input — use first row for explanation.
    X_prepared = X[feature_names].iloc[:1]
    xv = X_prepared.to_numpy(dtype=float)

    shap_values = explainer.shap_values(xv)
    base_value = float(explainer.expected_value)

    # shap_values shape: (1, n_features) for single output.
    sv = shap_values[0] if shap_values.ndim == 2 else shap_values
    feature_vals = xv[0]

    # Build attribution list.
    attributions: list[FeatureAttribution] = []
    for i, fname in enumerate(feature_names):
        attr = FeatureAttribution(
            feature=fname,
            value=float(feature_vals[i]) if not np.isnan(feature_vals[i]) else 0.0,
            shap_value=float(sv[i]),
            abs_shap=abs(float(sv[i])),
        )
        attributions.append(attr)

    # Sort by absolute impact.
    attributions.sort(key=lambda a: a.abs_shap, reverse=True)

    # Split into positive/negative drivers.
    positive = [a for a in attributions if a.shap_value > 0.005]
    negative = [a for a in attributions if a.shap_value < -0.005]

    predicted_return = base_value + sum(a.shap_value for a in attributions)

    return Explanation(
        instrument_id=instrument_id,
        horizon=horizon,
        predicted_return=predicted_return,
        base_value=base_value,
        attributions=attributions,
        top_positive=positive[:top_k],
        top_negative=negative[:top_k],
        model_version=model_version,
    )


def explain_batch(
    forecaster: GradientBoostingForecaster,
    X: pd.DataFrame,
    instrument_ids: Sequence[str],
    *,
    horizon: str = "",
    model_version: Optional[str] = None,
    top_k: int = 5,
) -> list[Explanation]:
    """Compute SHAP explanations for a batch of predictions."""
    import shap

    model = _get_median_model(forecaster)
    feature_names = forecaster.feature_names

    explainer = shap.TreeExplainer(model)
    X_prepared = X[feature_names]
    xv = X_prepared.to_numpy(dtype=float)

    shap_values = explainer.shap_values(xv)
    base_value = float(explainer.expected_value)

    explanations: list[Explanation] = []
    for row_idx in range(len(X_prepared)):
        sv = shap_values[row_idx]
        feature_vals = xv[row_idx]

        attributions: list[FeatureAttribution] = []
        for i, fname in enumerate(feature_names):
            attr = FeatureAttribution(
                feature=fname,
                value=float(feature_vals[i]) if not np.isnan(feature_vals[i]) else 0.0,
                shap_value=float(sv[i]),
                abs_shap=abs(float(sv[i])),
            )
            attributions.append(attr)

        attributions.sort(key=lambda a: a.abs_shap, reverse=True)
        positive = [a for a in attributions if a.shap_value > 0.005]
        negative = [a for a in attributions if a.shap_value < -0.005]
        predicted_return = base_value + sum(a.shap_value for a in attributions)

        explanations.append(Explanation(
            instrument_id=instrument_ids[row_idx] if row_idx < len(instrument_ids) else "",
            horizon=horizon,
            predicted_return=predicted_return,
            base_value=base_value,
            attributions=attributions,
            top_positive=positive[:top_k],
            top_negative=negative[:top_k],
            model_version=model_version,
        ))

    return explanations


def global_feature_importance(
    forecaster: GradientBoostingForecaster,
    X_sample: pd.DataFrame,
    *,
    max_samples: int = 200,
) -> dict[str, float]:
    """Compute mean |SHAP| across a sample for global feature ranking.

    Returns dict of feature_name -> mean_abs_shap, sorted descending.
    """
    import shap

    model = _get_median_model(forecaster)
    feature_names = forecaster.feature_names

    X_prepared = X_sample[feature_names].iloc[:max_samples]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_prepared.to_numpy(dtype=float))

    mean_abs = np.abs(shap_values).mean(axis=0)
    importance = {name: float(val) for name, val in zip(feature_names, mean_abs)}
    return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
