"""Drift monitoring: detect feature, target, and calibration drift.

Uses lightweight statistical tests (no Evidently dependency) to detect when
the data distribution has shifted enough to warrant retraining:

1. Feature drift: Population Stability Index (PSI) per feature.
2. Prediction drift: KS test on recent predictions vs training distribution.
3. Calibration drift: PICP (interval coverage) deviation from nominal.

When drift is detected, the module returns a DriftReport with affected features,
severity, and a recommendation (retrain / recalibrate / monitor).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from scipy import stats as sp_stats


@dataclass(frozen=True)
class FeatureDrift:
    """PSI result for one feature."""

    feature: str
    psi: float
    drifted: bool  # PSI > threshold
    severity: str  # "none", "warning", "critical"


@dataclass
class DriftReport:
    """Full drift assessment."""

    timestamp: str
    model_name: str
    horizon: str

    # Feature drift.
    feature_drifts: list[FeatureDrift] = field(default_factory=list)
    features_drifted_count: int = 0
    max_psi: float = 0.0

    # Prediction drift.
    prediction_ks_stat: float = 0.0
    prediction_ks_pvalue: float = 1.0
    prediction_drifted: bool = False

    # Calibration drift.
    nominal_coverage: float = 0.90
    empirical_coverage: float = 0.0
    calibration_drifted: bool = False
    coverage_gap: float = 0.0

    # Overall.
    needs_retrain: bool = False
    needs_recalibrate: bool = False
    recommendation: str = "monitor"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "model_name": self.model_name,
            "horizon": self.horizon,
            "feature_drift": {
                "drifted_count": self.features_drifted_count,
                "max_psi": round(self.max_psi, 4),
                "drifted_features": [
                    {"feature": fd.feature, "psi": round(fd.psi, 4), "severity": fd.severity}
                    for fd in self.feature_drifts if fd.drifted
                ],
            },
            "prediction_drift": {
                "ks_stat": round(self.prediction_ks_stat, 4),
                "ks_pvalue": round(self.prediction_ks_pvalue, 4),
                "drifted": self.prediction_drifted,
            },
            "calibration_drift": {
                "nominal_coverage": self.nominal_coverage,
                "empirical_coverage": round(self.empirical_coverage, 4),
                "drifted": self.calibration_drifted,
                "coverage_gap": round(self.coverage_gap, 4),
            },
            "needs_retrain": self.needs_retrain,
            "needs_recalibrate": self.needs_recalibrate,
            "recommendation": self.recommendation,
        }


# ---------------------------------------------------------------------------
# PSI (Population Stability Index)
# ---------------------------------------------------------------------------

def _compute_psi(
    reference: np.ndarray, current: np.ndarray, n_bins: int = 10
) -> float:
    """Compute PSI between reference and current distributions.

    PSI < 0.1: no significant drift
    PSI 0.1-0.25: moderate drift (warning)
    PSI > 0.25: significant drift (critical)
    """
    ref = reference[~np.isnan(reference)]
    cur = current[~np.isnan(current)]
    if len(ref) < 20 or len(cur) < 20:
        return 0.0

    # Create bins from reference distribution.
    breakpoints = np.quantile(ref, np.linspace(0, 1, n_bins + 1))
    breakpoints = np.unique(breakpoints)
    if len(breakpoints) < 3:
        return 0.0

    ref_counts = np.histogram(ref, bins=breakpoints)[0].astype(float)
    cur_counts = np.histogram(cur, bins=breakpoints)[0].astype(float)

    # Normalize to proportions, add small epsilon to avoid log(0).
    eps = 1e-6
    ref_pct = ref_counts / ref_counts.sum() + eps
    cur_pct = cur_counts / cur_counts.sum() + eps

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return max(0.0, psi)


def _psi_severity(psi: float) -> str:
    if psi > 0.25:
        return "critical"
    if psi > 0.1:
        return "warning"
    return "none"


# ---------------------------------------------------------------------------
# Main drift detection
# ---------------------------------------------------------------------------

PSI_THRESHOLD = 0.15  # trigger on moderate+ drift
KS_ALPHA = 0.05  # significance level for KS test
COVERAGE_TOLERANCE = 0.05  # ±5% from nominal is acceptable


def detect_drift(
    *,
    reference_features: np.ndarray,  # (n_ref, n_features)
    current_features: np.ndarray,  # (n_cur, n_features)
    feature_names: list[str],
    reference_predictions: Optional[np.ndarray] = None,  # (n_ref,)
    current_predictions: Optional[np.ndarray] = None,  # (n_cur,)
    actuals: Optional[np.ndarray] = None,  # realized values for calibration check
    predicted_lo: Optional[np.ndarray] = None,  # lower interval bound
    predicted_hi: Optional[np.ndarray] = None,  # upper interval bound
    nominal_coverage: float = 0.90,
    model_name: str = "",
    horizon: str = "",
    timestamp: str = "",
) -> DriftReport:
    """Run full drift detection suite.

    Args:
        reference_features: Training-time feature matrix.
        current_features: Recent (post-deploy) feature matrix.
        feature_names: Column names matching feature axis.
        reference_predictions: Predictions on training data (for KS).
        current_predictions: Recent predictions.
        actuals: Realized target values (for calibration check).
        predicted_lo: Lower interval bounds for actuals.
        predicted_hi: Upper interval bounds for actuals.
        nominal_coverage: Expected interval coverage (e.g., 0.90).
        model_name: For reporting.
        horizon: For reporting.
        timestamp: For reporting.

    Returns:
        DriftReport with per-feature PSI, prediction KS, calibration check.
    """
    report = DriftReport(
        timestamp=timestamp,
        model_name=model_name,
        horizon=horizon,
        nominal_coverage=nominal_coverage,
    )

    # --- Feature drift (PSI per feature) ---
    n_features = min(reference_features.shape[1], current_features.shape[1], len(feature_names))
    for i in range(n_features):
        ref_col = reference_features[:, i]
        cur_col = current_features[:, i]
        psi = _compute_psi(ref_col, cur_col)
        severity = _psi_severity(psi)
        drifted = psi > PSI_THRESHOLD
        report.feature_drifts.append(FeatureDrift(
            feature=feature_names[i],
            psi=psi,
            drifted=drifted,
            severity=severity,
        ))
        if drifted:
            report.features_drifted_count += 1
        report.max_psi = max(report.max_psi, psi)

    # --- Prediction drift (KS test) ---
    if reference_predictions is not None and current_predictions is not None:
        ref_p = reference_predictions[~np.isnan(reference_predictions)]
        cur_p = current_predictions[~np.isnan(current_predictions)]
        if len(ref_p) >= 10 and len(cur_p) >= 10:
            ks_result = sp_stats.ks_2samp(ref_p, cur_p)
            report.prediction_ks_stat = float(ks_result.statistic)
            report.prediction_ks_pvalue = float(ks_result.pvalue)
            report.prediction_drifted = report.prediction_ks_pvalue < KS_ALPHA

    # --- Calibration drift (coverage check) ---
    if actuals is not None and predicted_lo is not None and predicted_hi is not None:
        mask = ~(np.isnan(actuals) | np.isnan(predicted_lo) | np.isnan(predicted_hi))
        if mask.sum() >= 10:
            a = actuals[mask]
            lo = predicted_lo[mask]
            hi = predicted_hi[mask]
            inside = ((a >= lo) & (a <= hi)).mean()
            report.empirical_coverage = float(inside)
            report.coverage_gap = abs(float(inside) - nominal_coverage)
            report.calibration_drifted = report.coverage_gap > COVERAGE_TOLERANCE

    # --- Recommendation ---
    critical_features = sum(1 for fd in report.feature_drifts if fd.severity == "critical")
    if critical_features >= 3 or report.prediction_drifted:
        report.needs_retrain = True
        report.recommendation = "retrain"
    elif report.calibration_drifted:
        report.needs_recalibrate = True
        report.recommendation = "recalibrate"
    elif report.features_drifted_count >= 2:
        report.recommendation = "warning"
    else:
        report.recommendation = "monitor"

    return report
