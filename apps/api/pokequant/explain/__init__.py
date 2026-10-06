"""Explainability module: SHAP attributions + natural-language rationale."""

from pokequant.explain.shap_explain import (
    Explanation,
    FeatureAttribution,
    explain_prediction,
    global_feature_importance,
)
from pokequant.explain.narrative import generate_narrative

__all__ = [
    "Explanation",
    "FeatureAttribution",
    "explain_prediction",
    "global_feature_importance",
    "generate_narrative",
]
