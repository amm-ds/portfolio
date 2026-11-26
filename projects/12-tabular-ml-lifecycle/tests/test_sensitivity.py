"""Sensitivity-arm tests: timestamp-join lags, the keep-higher-MI pruning rule,
the reproduction gate (STOP condition), and the committed JSON artifact's shape.

Synthetic fixtures only — no network, no committed-artifact writes.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from tabular_ml_lifecycle.config import LifecycleConfig, MLPConfig
from tabular_ml_lifecycle.data import TARGET_COL, TIMESTAMP_COL, make_synthetic_frame, split_windows
from tabular_ml_lifecycle.features import apply_split, build_features, select_features
from tabular_ml_lifecycle.sensitivity import (
    REPRODUCTION_TOLERANCE,
    ReproductionError,
    run_ladder_arm,
    run_sensitivity,
)
from tabular_ml_lifecycle.stages import evaluate_core, features_core, prepare_core, train_core

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _gapped_frame(gap_start: int, gap_hours: int = 3, n_hours: int = 24 * 30) -> pd.DataFrame:
    """Hourly frame with ``gap_hours`` missing wall-clock hours from ``gap_start``.

    Counts are a deterministic function of the timestamp, so a timestamp-joined
    lag can be verified against the exact reference hour; the weather columns
    vary so correlation pruning stays well-defined.
    """
    ts = pd.date_range("2024-06-01", periods=n_hours, freq="h")
    keep = np.ones(n_hours, dtype=bool)
    keep[gap_start : gap_start + gap_hours] = False
    ts = ts[keep]
    n = len(ts)
    t = np.arange(n)
    temp = 0.5 + 0.2 * np.sin(t / 24.0)
    cnt = (ts.dayofyear.to_numpy() * 100 + ts.hour.to_numpy()).astype(float)
    return pd.DataFrame(
        {
            TIMESTAMP_COL: ts,
            "season": 2,
            "month": 6,
            "hour": ts.hour,
            "weekday": ts.dayofweek,
            "weathersit": 1,
            "holiday": 0,
            "workingday": (ts.dayofweek < 5).astype(int),
            "temp": temp,
            "atemp": temp * 0.98 + 0.01,
            "hum": 0.6 + 0.1 * np.cos(t / 12.0),
            "windspeed": 0.2 + 0.05 * np.sin(t / 6.0),
            TARGET_COL: cnt,
        }
    )


def test_timestamp_lags_join_on_wall_clock_hours() -> None:
    """lag_h at row t reads cnt[t - h hours] exactly; a missing reference hour is
    NaN, where the committed positional shift silently drifts to an earlier row."""
    frame = _gapped_frame(gap_start=200, gap_hours=3)
    featured = build_features(frame, [1, 24], lag_mode="timestamp")
    by_ts = frame.set_index(TIMESTAMP_COL)[TARGET_COL]
    for lag in (1, 24):
        joined = featured[f"cnt_lag_{lag}h"]
        expected = (frame[TIMESTAMP_COL] - pd.to_timedelta(lag, unit="h")).map(by_ts)
        assert np.array_equal(joined.to_numpy(), expected.to_numpy(), equal_nan=True)
    # the row right after the gap: positional lag_1h drifts to the last pre-gap
    # row (3 wall-clock hours earlier); the timestamp join says NaN.
    first_post_gap = int(frame.index[frame[TIMESTAMP_COL] == pd.Timestamp("2024-06-09 11:00")][0])
    assert np.isnan(featured["cnt_lag_1h"].iloc[first_post_gap])
    positional = build_features(frame, [1], lag_mode="positional")
    assert positional["cnt_lag_1h"].iloc[first_post_gap] == by_ts.iloc[first_post_gap - 1]
    # warm-up head: the first 24 rows have no t-24h inside the series
    assert featured["cnt_lag_24h"].iloc[:24].isna().all()


def test_variant_pruning_keeps_the_higher_mi_member(small_cfg: LifecycleConfig) -> None:
    """The keep_higher_mi rule keeps the higher-information member of every
    pruned pair; the committed rule keeps the other one."""
    frame = make_synthetic_frame(seed=7, n_days=140)
    windows = split_windows(len(frame), small_cfg.val_weeks, small_cfg.test_weeks)
    featured = build_features(frame, small_cfg.lag_hours, small_cfg.lag_mode)
    train, val, _ = apply_split(featured, windows, small_cfg.max_lag)

    committed = select_features(small_cfg, train, val, windows)
    variant_cfg = small_cfg.model_copy(update={"pruning_rule": "keep_higher_mi"})
    variant = select_features(variant_cfg, train, val, windows)

    assert committed.pruned_pairs and variant.pruned_pairs
    for pair in variant.pruned_pairs:
        kept, dropped = pair["kept"], pair["dropped"]
        assert variant.mi_scores[kept] >= variant.mi_scores[dropped]
        assert kept in variant.selected and dropped not in variant.selected
    for pair in committed.pruned_pairs:
        kept, dropped = pair["kept"], pair["dropped"]
        assert committed.mi_scores[kept] <= committed.mi_scores[dropped]
    # temp/atemp correlate above the threshold in the twin, so the two rules
    # must keep opposite members of that pair.
    committed_pair = next(
        p for p in committed.pruned_pairs if {p["kept"], p["dropped"]} == {"temp", "atemp"}
    )
    variant_pair = next(
        p for p in variant.pruned_pairs if {p["kept"], p["dropped"]} == {"temp", "atemp"}
    )
    assert committed_pair["kept"] == variant_pair["dropped"]
    assert variant.selected != committed.selected


def _variant_cfg(cfg: LifecycleConfig) -> LifecycleConfig:
    return cfg.model_copy(update={"lag_mode": "timestamp", "pruning_rule": "keep_higher_mi"})


@pytest.fixture(scope="module")
def small_committed_run(tmp_path_factory: pytest.TempPathFactory) -> LifecycleConfig:
    """A small synthetic 'committed' pipeline: prepare → features → train → evaluate."""
    cfg = LifecycleConfig(
        seed=7,
        data_source="synthetic",
        n_days_synthetic=140,
        val_weeks=2,
        test_weeks=2,
        rf_n_estimators=10,
        hpo_trials=5,
        hpo_time_budget_s=60,
        lgbm_n_estimators=50,
        lgbm_early_stopping=10,
        mlp=MLPConfig(hidden_dims=[8], embed_dim=4, max_epochs=4, patience=2, batch_size=64),
        bootstrap_resamples=100,
        learning_curve_fractions=[0.5, 1.0],
        data_dir=tmp_path_factory.mktemp("sens") / "data",
        reports_dir=tmp_path_factory.mktemp("sens") / "reports",
    )
    prepare_core(cfg)
    features_core(cfg)
    train_core(cfg)
    evaluate_core(cfg)
    return cfg


def test_sensitivity_reproduces_small_committed_run(small_committed_run: LifecycleConfig) -> None:
    """The re-derived arm must match the pipeline's own metrics.json within the
    gate tolerance, and the run writes only the sensitivity artifact."""
    cfg = small_committed_run
    metrics_path = cfg.reports_dir / "metrics.json"
    before = metrics_path.read_bytes()
    committed_mlp = json.loads(before)["mlp"]["mae"]

    out = run_sensitivity(cfg, _variant_cfg(cfg))
    assert out == cfg.reports_dir / "sensitivity_pruning_lags.json"
    payload = json.loads(out.read_text())

    repro = payload["reproduction"]
    assert repro["passed"] is True
    assert repro["expected_test_mae"] == pytest.approx(committed_mlp, abs=1e-12)
    assert repro["abs_diff"] <= REPRODUCTION_TOLERANCE
    assert payload["committed"]["rederived_max_abs_diff"] <= REPRODUCTION_TOLERANCE
    # committed metrics.json is byte-identical after the arm runs
    assert metrics_path.read_bytes() == before

    variant = payload["variant"]
    assert set(variant["test_mae"]) == {
        "seasonal_naive",
        "ridge",
        "random_forest",
        "lightgbm_hpo",
        "mlp",
    }
    assert all(v >= 0 for v in variant["test_mae"].values())
    deltas = payload["delta_variant_minus_committed"]["day_block"]
    assert set(deltas) == set(variant["test_mae"])
    for row in deltas.values():
        assert row["lo"] <= row["point"] <= row["hi"]
        assert row["n_boot"] == cfg.bootstrap_resamples
        assert row["block_hours"] == 24
    assert isinstance(payload["honest_note"]["triggered"], bool)
    assert (cfg.reports_dir / "figures" / "sensitivity_pruning_lags.json").exists()


def test_sensitivity_gate_fails_closed(small_committed_run: LifecycleConfig) -> None:
    """A committed MAE the pipeline cannot reproduce must abort the arm (STOP)."""
    cfg = small_committed_run
    derived = json.loads((cfg.reports_dir / "metrics.json").read_text())["mlp"]["mae"]
    with pytest.raises(ReproductionError, match="reproduction failed"):
        run_sensitivity(cfg, _variant_cfg(cfg), expected_mae=derived + 1.0)


def test_variant_arm_keeps_frozen_test_window_on_gaps(tmp_path: Path) -> None:
    """Timestamp lags on a gapped series: NaN-lag rows leave train/validation,
    but the frozen test window keeps every row (median-imputed lag cells)."""
    frame = _gapped_frame(gap_start=400, gap_hours=4)  # gap inside validation, <168h before test
    cfg = LifecycleConfig(
        seed=7,
        data_source="synthetic",
        val_weeks=1,
        test_weeks=1,
        rf_n_estimators=10,
        hpo_trials=5,
        hpo_time_budget_s=60,
        lgbm_n_estimators=50,
        lgbm_early_stopping=10,
        mlp=MLPConfig(hidden_dims=[8], embed_dim=4, max_epochs=4, patience=2, batch_size=64),
        bootstrap_resamples=100,
        learning_curve_fractions=[0.5, 1.0],
        lag_mode="timestamp",
        pruning_rule="keep_higher_mi",
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )
    cfg.data_dir.mkdir(parents=True)
    frame.to_parquet(cfg.data_dir / "hour.parquet", index=False)

    result = run_ladder_arm(cfg)
    windows = split_windows(len(frame), cfg.val_weeks, cfg.test_weeks)
    assert len(result.y_test) == windows.n_test  # frozen window untouched
    handling = result.nan_handling
    assert handling["train_rows_dropped"] + handling["val_rows_dropped"] > 0
    assert handling["test_lag_cells_median_imputed"] > 0
    for pred in result.test_preds.values():
        assert not np.isnan(pred).any()


def test_committed_sensitivity_artifact_shape() -> None:
    """The committed E4 artifact: gate passed, atemp kept, per-model deltas, and
    the committed metrics.json still carries the original headline MAE."""
    payload = json.loads((REPORTS_DIR / "sensitivity_pruning_lags.json").read_text())
    committed = json.loads((REPORTS_DIR / "metrics.json").read_text())

    assert committed["mlp"]["mae"] == pytest.approx(25.43163249606178, abs=1e-12)
    repro = payload["reproduction"]
    assert repro["passed"] is True
    assert repro["expected_test_mae"] == pytest.approx(committed["mlp"]["mae"], abs=1e-12)
    assert repro["abs_diff"] <= repro["tolerance"] == REPRODUCTION_TOLERANCE

    variant = payload["variant"]
    assert "atemp" in variant["selected_features"]
    assert "temp" not in variant["selected_features"]
    assert variant["nan_handling"]["test_lag_cells_median_imputed"] >= 0
    assert payload["committed"]["test_mae"]["mlp"] == pytest.approx(
        committed["mlp"]["mae"], abs=1e-12
    )
    deltas = payload["delta_variant_minus_committed"]["day_block"]
    assert set(deltas) == {"seasonal_naive", "ridge", "random_forest", "lightgbm_hpo", "mlp"}
    for row in deltas.values():
        assert row["lo"] <= row["point"] <= row["hi"]
        assert row["n_boot"] == 2000
    mlp = deltas["mlp"]
    assert payload["honest_note"]["triggered"] == (mlp["hi"] < 0.0)
