"""Wave-23 roadmap round: the non-degenerate sparse interval (nowcast track)
and the cost-aware routing arm (multi-step track) — formulas pinned on tiny
hand cases, plus the selection-only leakage property of the cost-aware rule.
"""

import json

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.probabilistic import run_probabilistic, sparse_history_band

MS_CONFIG = ForecastConfig(
    n_days=150,
    n_stores=2,
    n_products=2,
    lags=[1, 7],
    n_splits=3,
    gap=3,
    min_train_size=30,
    multistep_horizons=[1, 7, 14],
    multistep_n_origins=8,
    multistep_test_origins=2,
    multistep_window_days=14,
    bootstrap_reps=200,
)


def _mixed_panel() -> pl.DataFrame:
    """4 series: two smooth (daily demand), one intermittent, one lumpy."""
    dates = np.arange(
        np.datetime64("2024-01-01"), np.datetime64("2024-05-29"), dtype="datetime64[D]"
    )
    n = len(dates)
    rng = np.random.default_rng(5)
    smooth_a = rng.poisson(8.0, n).astype(float)
    smooth_b = 5.0 + 3.0 * np.sin(np.arange(n) * 2 * np.pi / 7) + rng.poisson(2, n)
    intermittent = np.zeros(n)
    intermittent[::5] = 6.0  # every 5th day -> ADI = 5, CV^2 = 0
    lumpy = np.zeros(n)
    idx = np.flatnonzero(rng.random(n) < 0.15)
    lumpy[idx] = rng.integers(1, 30, idx.size).astype(float)
    frames = []
    for store, product, units in (
        ("s0", "p0", smooth_a),
        ("s0", "p1", smooth_b),
        ("s1", "p0", intermittent),
        ("s1", "p1", lumpy),
    ):
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": store,
                    "product": product,
                    "units": units.astype(int),
                }
            )
        )
    return pl.concat(frames)


@pytest.fixture
def mixed_panel() -> pl.DataFrame:
    return _mixed_panel()


# ---------------------------------------------------------------------------
# sparse_history_band: hand-computed
# ---------------------------------------------------------------------------


def test_sparse_history_band_hand_computed() -> None:
    """Predicted-zero rows take [0, series-history q80]; predicted-nonzero
    rows keep the zero-aware ±width; absent series fall back to the pooled q80."""
    hist_a = np.array([0.0, 0.0, 1.0, 2.0, 0.0, 4.0, 0.0, 8.0])  # q80 = 6.4
    hist_b = np.array([3.0, 1.0, 2.0])  # unused: B absent from the last fold
    cal_y = np.concatenate([hist_a, hist_b])
    cal_series = np.array(["A"] * len(hist_a) + ["B"] * len(hist_b))
    last = {
        "series": np.array(["A", "A", "C", "D"]),
        "p50": np.array([0.0, 0.0, 0.0, 2.0]),
        "y_true": np.array([0.0, 1.0, 0.0, 2.0]),
    }
    widths = np.array([0.0, 0.0, 1.0, 1.0])  # zero-aware widths per row
    lo, hi, summary = sparse_history_band(last, cal_series, cal_y, widths)

    q80_a = float(np.quantile(hist_a, 0.8))
    pooled_q80 = float(np.quantile(cal_y, 0.8))
    # A's predicted-zero rows: [0, q80 of A's history]
    assert lo[0] == 0.0 and hi[0] == pytest.approx(q80_a)
    assert lo[1] == 0.0 and hi[1] == pytest.approx(q80_a)
    # C (predicted zero, absent from calibration): pooled fallback
    assert lo[2] == 0.0 and hi[2] == pytest.approx(pooled_q80)
    # D (predicted nonzero): keeps the zero-aware ±width
    assert lo[3] == pytest.approx(1.0) and hi[3] == pytest.approx(3.0)  # 2.0 ± 1.0
    assert hi[3] - lo[3] > 0
    # band strictly wider than the zero-aware [p50, p50] wherever history saw demand
    assert hi[0] > 0.0
    assert summary["zero_rows"] == 3
    assert summary["nonzero_rows"] == 1
    assert summary["fallback_series"] == 1
    assert pooled_q80 > 0


def test_run_probabilistic_writes_sparse_history_band(
    settings: DemandSettings, config: ForecastConfig, features: pl.DataFrame
) -> None:
    """The wave-23 block lands in probabilistic.json with coverage AND width."""
    from demand_forecasting.features import save_features

    save_features(features, settings)
    result = run_probabilistic(settings, config)
    block = result["sparse_history_band"]
    assert 0.0 <= block["coverage_last_fold"] <= 1.0
    assert block["avg_width_last_fold"] >= 0.0
    assert block["calibration_verdict"] in {"calibrated", "conservative", "optimistic"}
    assert "vs_zero_aware" in block
    persisted = json.loads((settings.reports_dir / "probabilistic.json").read_text())
    assert "sparse_history_band" in persisted
    assert len(persisted["sparse_history_band"]["horizon_coverage"]) == 14


# ---------------------------------------------------------------------------
# Cost-aware routing arm: block shape + selection-only property
# ---------------------------------------------------------------------------


def test_cost_aware_routing_block(mixed_panel: pl.DataFrame) -> None:
    from demand_forecasting.multihorizon import run_multistep

    result = run_multistep(settings=DemandSettings(), config=MS_CONFIG, panel=mixed_panel)
    block = result.block["routing"]["cost_aware"]
    assert block["service_level"] == 0.90
    assert block["simulation"] is True
    # every series routed, pools respected
    assert len(block["method_choices"]) == 4
    pool = set(result.block["routing"]["pool_sparse"]) | set(result.block["routing"]["pool_dense"])
    assert set(block["method_choices"].values()) <= pool
    # the rule's own objective: cost-routed never costs more on the selection
    # origins than the MAE-routed champion (it won there by construction)
    sel = block["selection_cost_at_routing_level"]
    assert sel["routed_cost"] <= sel["routed"] + 1e-9
    # scored-once test-arm numbers exist (MAE + newsvendor per class per q)
    overall = block["overall_mae_test"]
    assert overall["routed_cost"] >= 0.0 and overall["routed"] >= 0.0
    assert "ci95" in overall["routed_cost_minus_routed"]
    for _cls, entry in block["per_class"].items():
        assert set(entry["mae"]) >= {"routed_cost", "routed", "routed_cost_minus_routed"}
        for q_key, q_entry in entry["newsvendor_per_unit_demand"].items():
            assert q_key.startswith("q_")
            assert q_entry["routed_cost_per_unit_demand"] >= 0.0
            assert q_entry["routed_per_unit_demand"] >= 0.0
        assert isinstance(entry["method_choices"], dict)


def test_cost_aware_routing_uses_selection_origins_only(mixed_panel: pl.DataFrame) -> None:
    """Tainting the last test window leaves the cost-aware picks unchanged."""
    from demand_forecasting.multihorizon import (
        multistep_origin_indices,
        panel_matrix,
        run_multistep,
        split_origins,
    )

    dates, _series_ids, units = panel_matrix(mixed_panel)
    origins = multistep_origin_indices(len(dates), MS_CONFIG)
    _, test = split_origins(origins, MS_CONFIG)
    rng = np.random.default_rng(11)

    result = run_multistep(settings=DemandSettings(), config=MS_CONFIG, panel=mixed_panel)
    choices_before = dict(result.block["routing"]["cost_aware"]["method_choices"])

    tainted_units = units.copy()
    last = test[-1]
    window = tainted_units[last + 1 : last + 15].copy()
    tainted_units[last + 1 : last + 15] = rng.permutation(window.ravel()).reshape(window.shape)
    frames = []
    for k, (store, product) in enumerate((("s0", "p0"), ("s0", "p1"), ("s1", "p0"), ("s1", "p1"))):
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": store,
                    "product": product,
                    "units": tainted_units[:, k].astype(int),
                }
            )
        )
    tainted_panel = pl.concat(frames)
    result2 = run_multistep(settings=DemandSettings(), config=MS_CONFIG, panel=tainted_panel)
    assert result2.block["routing"]["cost_aware"]["method_choices"] == choices_before
