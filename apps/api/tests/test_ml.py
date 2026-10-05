from __future__ import annotations

import numpy as np
import pandas as pd

from pokequant.domain.enums import Horizon
from pokequant.ml.baselines import DriftForecaster, NaiveForecaster
from pokequant.ml.dataset import build_dataset
from pokequant.ml.evaluate import (
    compute_metrics,
    directional_accuracy,
    evaluate_forecaster,
    time_series_folds,
)
from pokequant.ml.forecast import forecast_instrument
from pokequant.ml.gbm import GBMConfig, GradientBoostingForecaster
from pokequant.ml.registry import FileModelRegistry
from pokequant.ml.train import train_and_register


def test_naive_predicts_zero(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    model = NaiveForecaster(90)
    model.fit(ds)
    preds = model.predict_return(ds.X)
    assert np.allclose(preds, 0.0)


def test_drift_uses_trailing_return(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    model = DriftForecaster(90)
    model.fit(ds)
    preds = model.predict_return(ds.X)
    expected = np.nan_to_num(ds.X["ret_90"].to_numpy() / 90.0) * 90
    assert np.allclose(preds, expected)


def test_baseline_quantiles_monotone(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    model = NaiveForecaster(90)
    model.fit(ds)
    q = model.predict_quantiles(ds.X, [0.1, 0.5, 0.9])
    assert (q[0.1] <= q[0.5]).all() and (q[0.5] <= q[0.9]).all()


def test_gbm_fit_predict_and_monotone_quantiles(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    model = GradientBoostingForecaster(GBMConfig(n_estimators=60))
    model.fit(ds)
    preds = model.predict_return(ds.X.iloc[:50])
    assert preds.shape == (50,)
    q = model.predict_quantiles(ds.X.iloc[:50], [0.1, 0.5, 0.9])
    assert (q[0.1] <= q[0.5] + 1e-9).all()
    assert (q[0.5] <= q[0.9] + 1e-9).all()


def test_gbm_deterministic(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    a = GradientBoostingForecaster(GBMConfig(n_estimators=40))
    b = GradientBoostingForecaster(GBMConfig(n_estimators=40))
    a.fit(ds)
    b.fit(ds)
    assert np.allclose(a.predict_return(ds.X.iloc[:20]), b.predict_return(ds.X.iloc[:20]))


def test_time_series_folds_have_no_leakage(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    folds = time_series_folds(ds.as_of, n_splits=3, horizon_days=90, embargo_days=5)
    assert folds
    values = pd.to_datetime(ds.as_of).to_numpy()
    for train_idx, test_idx in folds:
        train_max = values[train_idx].max()
        test_min = values[test_idx].min()
        gap = (test_min - train_max) / np.timedelta64(1, "D")
        assert gap >= 95  # horizon(90) + embargo(5)


def test_compute_metrics_basic() -> None:
    y_true = np.array([0.1, -0.2, 0.05])
    y_pred = np.array([0.05, -0.1, 0.02])
    m = compute_metrics(y_true, y_pred, np.array([-0.3, -0.4, -0.1]), np.array([0.3, 0.1, 0.2]))
    assert m["rmse"] > 0
    assert m["picp"] == 1.0  # all inside
    assert 0.0 <= m["directional_accuracy"] <= 1.0


def test_directional_accuracy_perfect() -> None:
    y = np.array([1.0, -1.0, 2.0])
    assert directional_accuracy(y, y) == 1.0


def test_evaluate_forecaster_runs(multi_history: tuple[dict, dict]) -> None:
    histories, releases = multi_history
    ds = build_dataset(histories, releases, 90)
    metrics = evaluate_forecaster(lambda: NaiveForecaster(90), ds, n_splits=3)
    assert metrics["n_folds"] >= 1
    assert "rmse" in metrics


def test_registry_roundtrip(tmp_path) -> None:
    reg = FileModelRegistry(tmp_path / "models")
    model = NaiveForecaster(90)
    v1 = reg.save("m", model, {"horizon": "d90"})
    assert reg.get_production_version("m") == v1.version
    loaded, meta = reg.load("m")
    assert isinstance(loaded, NaiveForecaster)
    assert meta["horizon"] == "d90"


def test_train_and_register_end_to_end(multi_history: tuple[dict, dict], tmp_path) -> None:
    histories, releases = multi_history
    reg = FileModelRegistry(tmp_path / "models")
    report = train_and_register(
        histories, releases, Horizon.D90, reg, n_splits=3, gbm_config=GBMConfig(n_estimators=60)
    )
    assert report.model_version is not None
    assert "gbm" in report.metrics and "naive" in report.metrics
    # Production model loads and forecasts.
    model, card = reg.load(report.model_name)
    result = forecast_instrument(
        model, "A", histories["A"], releases["A"], Horizon.D90, quantiles=card["quantiles"]
    )
    assert result is not None
    assert result.predicted_price > 0
    assert set(result.quantiles_price) == set(card["quantiles"])
