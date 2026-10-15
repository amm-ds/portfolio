"""Time-CV integration: splits must be leakage-free at date granularity."""

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import ForecastConfig
from demand_forecasting.evaluate import _date_positions, _mae, backtest, best_model
from portfolio_core.timecv import TimeSeriesCV


def test_time_series_cv_no_leakage() -> None:
    """Train indices must end strictly before validation starts (plus gap)."""
    cv = TimeSeriesCV(n_splits=4, gap=7)
    n = 500
    for fold in cv.split(n):
        assert fold.train_idx.max() < fold.val_idx.min()
        assert fold.val_start - fold.train_end == 7  # embargo gap enforced
        assert not np.intersect1d(fold.train_idx, fold.val_idx).size


def test_backtest_splits_are_date_aligned(features: pl.DataFrame, config: ForecastConfig) -> None:
    """Row-level train/val masks derived from date folds never overlap in time."""
    pos = _date_positions(features)
    cv = TimeSeriesCV(
        n_splits=config.n_splits, gap=config.gap, min_train_size=config.min_train_size
    )
    n_dates = int(pos.max()) + 1
    for fold in cv.split(n_dates):
        train_rows = np.flatnonzero(pos < fold.train_end)
        val_rows = np.flatnonzero(
            (pos >= fold.val_start) & (pos < fold.val_start + fold.val_idx.size)
        )
        assert train_rows.max() < val_rows.min()
        # every validation row is strictly after the newest training date
        dates = features["date"].to_numpy()
        assert dates[train_rows].max() < dates[val_rows].min()


def test_backtest_runs_all_models(features: pl.DataFrame, config: ForecastConfig) -> None:
    """The backtest produces one run per model (2 naives + ridge + 4 boosters + NN)."""
    result = backtest(features, config)
    assert {r.name for r in result.runs} == {
        "naive_mean",
        "naive_last",
        "ridge",
        "hgb",
        "hgb_tuned",
        "xgb_tuned",
        "lgbm_tuned",
        "temporal_net",
    }
    for run in result.runs:
        mae = run.get("mae")
        assert mae is not None and mae.value > 0
        rmse = run.get("rmse")
        assert rmse is not None and rmse.value >= mae.value
    assert len(result.folds) == config.n_splits * 8


def test_naive_baselines_are_sane(features: pl.DataFrame, config: ForecastConfig) -> None:
    """naive_mean predicts a constant; naive_last tracks the previous day."""
    result = backtest(features, config)
    mean_run = result.last_fold("naive_mean")
    assert len(set(mean_run.y_pred.tolist())) == 1  # one global number
    last_run = result.last_fold("naive_last")
    assert not np.allclose(last_run.y_pred, last_run.y_true)  # persistence ≠ perfect
    # persistence error is the day-over-day demand change — non-zero on real series
    assert last_run.mae > 0


def test_learners_beat_naives(features: pl.DataFrame, config: ForecastConfig) -> None:
    """The trained models must clear the naive floor on pooled out-of-fold MAE."""
    result = backtest(features, config)
    naive_floor = min(_mae(result, n) for n in ("naive_mean", "naive_last"))
    assert _mae(result, best_model(result)) < naive_floor


def test_cv_rejects_impossible_config() -> None:
    """Too few samples for the requested splits/gap must fail loudly."""
    cv = TimeSeriesCV(n_splits=4, gap=7)
    with pytest.raises(ValueError, match="too small"):
        list(cv.split(10))


def test_min_train_size_enforced() -> None:
    cv = TimeSeriesCV(n_splits=2, gap=0, min_train_size=100)
    with pytest.raises(ValueError, match="min_train_size"):
        list(cv.split(120))
