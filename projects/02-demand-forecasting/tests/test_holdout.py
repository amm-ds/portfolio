"""Frozen holdout protocol: the test window can never influence selection.

The champion pick must pool folds 1..n-1 ONLY. The property is tested the
direct way: shuffling the test fold's actuals leaves the selection result
bit-identical, and the committed selection agrees with a hand-computed pool
over the selection folds.
"""

import json

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import (
    EVAL_HORIZON_DAYS,
    backtest,
    best_model,
    evaluate,
    strongest_naive,
)
from demand_forecasting.model import model_specs
from portfolio_eval.ml import regression_metrics

FAST_SPECS = {"naive_mean", "naive_last", "ridge"}


def _fast_backtest(features: pl.DataFrame, config: ForecastConfig):
    specs = [s for s in model_specs() if s.name in FAST_SPECS]
    return backtest(features, config, specs=specs)


def _hand_pooled_mae(result, model: str, fold_ids: set[int]) -> float:
    """Reference pooled MAE straight from the fold records."""
    recs = [f for f in result.folds if f.model == model and f.fold in fold_ids]
    total = sum(float(np.abs(r.y_true - r.y_pred).sum()) for r in recs)
    count = sum(r.y_true.size for r in recs)
    return total / count


def test_selection_uses_only_origins_1_to_n_minus_1(
    features: pl.DataFrame, config: ForecastConfig
) -> None:
    result = _fast_backtest(features, config)
    selection = set(result.selection_fold_ids())
    expected = min(
        (r.name for r in result.runs if "naive" not in r.name),
        key=lambda n: _hand_pooled_mae(result, n, selection),
    )
    assert result.selection_fold_ids() == list(range(result.test_fold_id()))
    assert best_model(result) == expected


def test_shuffling_test_fold_does_not_change_selection(
    features: pl.DataFrame, config: ForecastConfig
) -> None:
    """The P0 proof: permute the test window's actuals — the pick must not move."""
    result = _fast_backtest(features, config)
    champion_before = best_model(result)
    naive_before = strongest_naive(result)
    selection_maes_before = {
        r.name: result.pooled_mae(r.name, set(result.selection_fold_ids())) for r in result.runs
    }

    rng = np.random.default_rng(123)
    test_id = result.test_fold_id()
    for rec in result.folds:
        if rec.fold == test_id:
            rec.y_true = rng.permutation(rec.y_true)

    assert best_model(result) == champion_before
    assert strongest_naive(result) == naive_before
    assert selection_maes_before == {
        r.name: result.pooled_mae(r.name, set(result.selection_fold_ids())) for r in result.runs
    }


def test_headline_is_test_window_and_legacy_is_pooled(
    features: pl.DataFrame, config: ForecastConfig
) -> None:
    result = _fast_backtest(features, config)
    test_id = result.test_fold_id()
    for run in result.runs:
        rec = next(f for f in result.folds if f.model == run.name and f.fold == test_id)
        by_name = {m.name: m.value for m in run.metrics}
        expected = regression_metrics(rec.y_true.tolist(), rec.y_pred.tolist())
        assert by_name["mae"] == pytest.approx(next(m.value for m in expected if m.name == "mae"))
        # legacy pooled = ALL folds (selection + test), the pre-holdout headline
        all_ids = {f.fold for f in result.folds if f.model == run.name}
        assert by_name["legacy_pooled_mae"] == pytest.approx(
            _hand_pooled_mae(result, run.name, all_ids)
        )
        # the fold/horizon suite is present and well-shaped
        assert len(result.fold_maes()[run.name]) == config.n_splits
        assert len(result.horizon_mae[run.name]) == EVAL_HORIZON_DAYS
        assert len(result.horizon_mase[run.name]) == EVAL_HORIZON_DAYS
        assert by_name["wape"] == pytest.approx(
            float(np.abs(rec.y_true - rec.y_pred).sum() / np.abs(rec.y_true).sum())
        )
        assert by_name["bias"] == pytest.approx(float(np.mean(rec.y_pred - rec.y_true)))


def test_horizon_mase_zero_scale_excluded() -> None:
    """Series without a seasonal scale are excluded from horizon MASE, not infinite."""
    from demand_forecasting.evaluate import _horizon_metrics

    dates = np.arange("2024-01-01", "2024-01-15", dtype="datetime64[D]")
    series = np.array(["a"] * 14)
    err = np.ones(14)
    mae, mase = _horizon_metrics(dates, series, err, scales={"a": 0.0})
    assert mae[0] == pytest.approx(1.0)
    assert np.isnan(mase[0])  # no seasonal scale -> excluded, not infinite


def test_evaluate_writes_metadata_and_metric_suite(
    settings: DemandSettings, config: ForecastConfig, features: pl.DataFrame
) -> None:
    from demand_forecasting.data import prepare
    from demand_forecasting.features import save_features

    prepare(settings, config)
    save_features(features, settings)
    result = evaluate(settings, config)
    del result

    meta = json.loads((settings.reports_dir / "evaluation_metadata.json").read_text())
    n_folds = config.n_splits
    assert meta["protocol"] == "rolling_origin_holdout_v1"
    assert meta["rolling_origin"]["n_origins"] == n_folds
    assert meta["rolling_origin"]["horizon_days"] == EVAL_HORIZON_DAYS
    assert meta["selection_used_origins"] == list(range(1, n_folds))
    assert meta["test_origin"] == n_folds
    assert meta["selection_used_origins"] != [meta["test_origin"]]
    assert "fit within the training window of each fold" in meta["preprocessing_statement"]
    for name in ("mae", "mase", "bias", "wape", "horizon_mae"):
        assert name in meta["metric_definitions"]

    metrics = json.loads((settings.reports_dir / "metrics.json").read_text())
    assert metrics["_meta"]["protocol"] == "rolling_origin_holdout_v1"
    assert metrics["_meta"]["best_model"] == meta["best_model"]
    assert metrics["_meta"]["selection_used_origins"] == meta["selection_used_origins"]
    assert metrics["_meta"]["test_origin"] == meta["test_origin"]
    for block in metrics.values():
        if not isinstance(block, dict) or "mae" not in block:
            continue
        assert len(block["fold_maes"]) == n_folds
        assert len(block["horizon_mae"]) == EVAL_HORIZON_DAYS
        assert len(block["horizon_mase"]) == EVAL_HORIZON_DAYS
        assert "legacy_pooled_mae" in block  # pre-holdout headline retained
