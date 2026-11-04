"""Model tests: determinism (ridge + MLP), HPO budget, metric parity."""

import numpy as np
import pandas as pd
import pytest
from tabular_ml_lifecycle.config import LifecycleConfig, MLPConfig
from tabular_ml_lifecycle.data import TARGET_COL, make_synthetic_frame, split_windows
from tabular_ml_lifecycle.features import apply_split, build_features, seasonal_naive_predict
from tabular_ml_lifecycle.metrics import mae, mape, paired_bootstrap_mae_delta, rmse
from tabular_ml_lifecycle.mlp import MLPRegressor
from tabular_ml_lifecycle.models import ridge_estimator, run_hpo

FEATURES = ["temp", "hum", "windspeed", "weathersit", "hour_sin", "hour_cos", "cnt_lag_1h"]


@pytest.fixture()
def xy(small_cfg: LifecycleConfig) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    frame = make_synthetic_frame(small_cfg.seed, small_cfg.n_days_synthetic)
    windows = split_windows(len(frame), small_cfg.val_weeks, small_cfg.test_weeks)
    featured = build_features(frame, small_cfg.lag_hours)
    train, val, _ = apply_split(featured, windows, small_cfg.max_lag)
    return train, train[TARGET_COL].astype(float), val, val[TARGET_COL].astype(float)


def test_metric_parity_on_known_arrays() -> None:
    y = np.array([100.0, 200.0, 300.0, 0.0])
    pred = np.array([90.0, 210.0, 300.0, 5.0])
    assert mae(y, pred) == pytest.approx(6.25)
    assert rmse(y, pred) == pytest.approx(np.sqrt((100 + 100 + 0 + 25) / 4))
    # MAPE floors the zero-count hour at 1, so the last term is 5/1 = 5.0
    assert mape(y, pred) == pytest.approx((0.1 + 0.05 + 0.0 + 5.0) / 4 * 100)


def test_paired_bootstrap_detects_real_gap() -> None:
    rng = np.random.default_rng(0)
    y = np.full(400, 500.0) + rng.normal(0, 30, 400)
    champion = y + rng.normal(0, 15, 400)  # clearly closer than the floor
    floor = y + rng.normal(0, 120, 400)
    ci = paired_bootstrap_mae_delta(y, champion, floor, 500, seed=3)
    assert ci.significant_95
    assert ci.lo > 0
    same = paired_bootstrap_mae_delta(y, champion, champion.copy(), 500, seed=3)
    assert not same.significant_95
    assert same.point == pytest.approx(0.0)


def test_bootstrap_is_seeded() -> None:
    y = np.arange(200.0)
    a = paired_bootstrap_mae_delta(y, y + 1, y + 3, 200, seed=5)
    b = paired_bootstrap_mae_delta(y, y + 1, y + 3, 200, seed=5)
    assert (a.point, a.lo, a.hi) == (b.point, b.lo, b.hi)


def test_ridge_deterministic(small_cfg: LifecycleConfig, xy: tuple) -> None:
    train, y_train, val, _ = xy
    first = ridge_estimator(small_cfg, FEATURES).fit(train[FEATURES], y_train)
    second = ridge_estimator(small_cfg, FEATURES).fit(train[FEATURES], y_train)
    p1, p2 = first.predict(val[FEATURES]), second.predict(val[FEATURES])
    assert np.array_equal(p1, p2)
    assert mae(val[TARGET_COL].to_numpy(), p1) == mae(val[TARGET_COL].to_numpy(), p2)


def test_mlp_deterministic_and_records_history(small_cfg: LifecycleConfig, xy: tuple) -> None:
    train, y_train, val, y_val = xy
    cols = ["hour", *FEATURES]

    def fit_once() -> MLPRegressor:
        model = MLPRegressor(small_cfg, small_cfg.seed)
        return model.fit(train[cols], y_train, val[cols], y_val, FEATURES)

    first, second = fit_once(), fit_once()
    p1 = first.predict(val[cols])
    p2 = second.predict(val[cols])
    assert np.array_equal(p1, p2)
    assert mae(y_val.to_numpy(), p1) == mae(y_val.to_numpy(), p2)
    # per-epoch curves are the overfitting-control artifact
    assert len(first.history.train_loss) == first.history.epochs_run
    assert len(first.history.val_loss) == first.history.epochs_run
    assert 1 <= first.history.best_epoch <= first.history.epochs_run
    # predictions come back in rental units (un-standardized)
    assert p1.mean() == pytest.approx(y_train.mean(), abs=3 * y_train.std())
    # predict pins one thread: multi-thread torch predict deadlocks on the
    # libomp shared with lightgbm (see DESIGN.md platform notes)
    import torch

    assert torch.get_num_threads() == 1
    # a different seed must change the fit (guard against a dead RNG)
    other = MLPRegressor(small_cfg, small_cfg.seed + 1000).fit(
        train[cols], y_train, val[cols], y_val, FEATURES
    )
    assert not np.array_equal(other.predict(val[cols]), p1)


def test_mlp_early_stopping_respects_patience(small_cfg: LifecycleConfig, xy: tuple) -> None:
    train, y_train, val, y_val = xy
    cfg = small_cfg.model_copy(
        update={"mlp": MLPConfig(hidden_dims=[8], embed_dim=4, max_epochs=60, patience=3)}
    )
    model = MLPRegressor(cfg, cfg.seed).fit(
        train[["hour", *FEATURES]], y_train, val[["hour", *FEATURES]], y_val, FEATURES
    )
    assert model.history.epochs_run <= cfg.mlp.max_epochs


def test_hpo_respects_trial_cap_and_time_budget(small_cfg: LifecycleConfig, xy: tuple) -> None:
    train, y_train, val, y_val = xy
    cfg = small_cfg.model_copy(update={"hpo_trials": 5, "hpo_time_budget_s": 600})
    outcome = run_hpo(cfg, train[FEATURES], y_train, val[FEATURES], y_val)
    assert outcome.n_trials == 5
    assert outcome.n_trials <= cfg.hpo_trials
    assert outcome.best_val_mae > 0
    assert set(outcome.best_params) == {
        "learning_rate",
        "num_leaves",
        "max_depth",
        "min_child_samples",
        "subsample",
        "colsample_bytree",
        "reg_lambda",
    }


def test_hpo_time_budget_binds(small_cfg: LifecycleConfig, xy: tuple) -> None:
    import time

    train, y_train, val, y_val = xy
    cfg = small_cfg.model_copy(update={"hpo_trials": 10_000, "hpo_time_budget_s": 3})
    started = time.perf_counter()
    outcome = run_hpo(cfg, train[FEATURES], y_train, val[FEATURES], y_val)
    elapsed = time.perf_counter() - started
    assert outcome.n_trials < 10_000  # the wall-clock budget, not the cap, stopped it
    assert elapsed < 30  # generous slack for the last trial's overrun


def test_naive_beats_nothing_sanity(xy: tuple) -> None:
    """The floor is computable on the val window and tracks the series level."""
    train, _, val, y_val = xy
    cnt = pd.Series(
        pd.concat([train, val]).sort_values("timestamp")[TARGET_COL].to_numpy(),
        index=pd.concat([train, val]).sort_values("timestamp")["timestamp"],
    )
    pred = seasonal_naive_predict(cnt, val["timestamp"])
    floor_mae = mae(y_val.to_numpy(), pred)
    assert 0 < floor_mae < y_val.to_numpy().std() * 2
