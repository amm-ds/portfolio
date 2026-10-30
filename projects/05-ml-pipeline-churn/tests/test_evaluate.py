"""End-to-end evaluation on a small config, plus cost/calibration unit tests."""

import json
from pathlib import Path

import numpy as np
import pytest
from churn_pipeline.cli import evaluate_core, prepare_core, train_core
from churn_pipeline.config import ChurnConfig
from churn_pipeline.evaluate import (
    artifact_paths,
    business_cost,
    cost_curve,
    expected_calibration_error,
    naive_majority_run,
    net_benefit,
    paired_bootstrap_cost_delta,
)


def test_business_cost_weights_misses_more() -> None:
    y_true = np.array([1, 1, 0, 0])
    proba = np.array([0.9, 0.1, 0.9, 0.1])  # 1 FP, 1 FN at t=0.5
    assert business_cost(y_true, proba, 0.5, fp_cost=1.0, fn_cost=5.0) == 6.0
    assert business_cost(y_true, proba, 0.5, fp_cost=1.0, fn_cost=1.0) == 2.0


def test_cost_curve_optimum_inside_grid(small_cfg: ChurnConfig) -> None:
    y_true = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    proba = np.array([0.1, 0.4, 0.35, 0.8, 0.2, 0.7, 0.05, 0.55])
    costs, optimal = cost_curve(small_cfg, y_true, proba)
    assert len(costs) == len(small_cfg.threshold_grid)
    assert optimal in small_cfg.threshold_grid
    assert costs.min() <= costs[0] and costs.min() <= costs[-1]


def test_ece_zero_for_perfect_calibration() -> None:
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
    proba = y_true.astype(float)
    assert expected_calibration_error(y_true, proba, n_bins=5) == pytest.approx(0.0)


def test_ece_positive_for_miscalibration() -> None:
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    proba = np.array([0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9])  # inverted confidence
    assert expected_calibration_error(y_true, proba, n_bins=4) == pytest.approx(0.1)
    confident = np.array([0.45, 0.45, 0.45, 0.45, 0.55, 0.55, 0.55, 0.55])
    assert expected_calibration_error(y_true, confident, n_bins=4) > 0.4


def test_net_benefit_matches_treat_all_formula() -> None:
    y_true = np.array([0, 0, 1, 1])
    proba = np.ones(4)  # predict everyone positive → treat-all
    for pt in (0.1, 0.3, 0.5, 0.7):
        expect = 0.5 - 0.5 * pt / (1 - pt)
        assert net_benefit(y_true, proba, pt) == pytest.approx(expect)


def test_paired_bootstrap_delta(small_cfg: ChurnConfig) -> None:
    """Seeded paired bootstrap: CI brackets the point delta; sign logic holds."""
    y_true = np.array([0, 0, 0, 1, 1, 1, 0, 1])
    good = np.array([0.1, 0.2, 0.1, 0.8, 0.9, 0.7, 0.3, 0.6])
    naive = np.full(8, 0.5)
    d1 = paired_bootstrap_cost_delta(
        small_cfg, y_true, good, naive, thr_a=0.5, thr_b=0.5, n_boot=500
    )
    d2 = paired_bootstrap_cost_delta(
        small_cfg, y_true, good, naive, thr_a=0.5, thr_b=0.5, n_boot=500
    )
    assert d1 == d2, "seeded bootstrap must be deterministic"
    assert d1["lo"] <= d1["point"] <= d1["hi"]
    assert d1["n_boot"] == 500
    # good model costs strictly less here, so the delta should be negative throughout
    assert d1["hi"] < 0 and d1["significant_95"]


def test_naive_majority_degenerates_to_constant_costs(small_cfg: ChurnConfig) -> None:
    """Constant base-rate probability: cheaper of alarm-all vs ignore-all."""
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    run, costs, optimal = naive_majority_run(small_cfg, y_true, 0.5)
    assert run.name == "naive_majority"
    n_pos, n_neg = 5, 5
    assert costs.min() == min(1.0 * n_neg, 5.0 * n_pos)
    cost = run.get("business_cost")
    assert cost is not None and cost.value == costs.min()
    auc = run.get("roc_auc")
    assert auc is not None and auc.value == 0.5
    assert optimal in small_cfg.threshold_grid


def test_end_to_end_cli_cores(small_cfg: ChurnConfig, params_file: Path) -> None:
    """prepare → train (HPO) → evaluate through the CLI cores (no network)."""
    prepare_core(small_cfg)
    train_core(small_cfg, params_file=params_file)
    report_path = evaluate_core(small_cfg)

    paths = artifact_paths(small_cfg)
    for key in ("logreg", "selected", "selected_calibrated", "holdout"):
        assert paths[key].exists(), key
    assert (small_cfg.data_dir / "churn.parquet").exists()
    assert (small_cfg.data_dir / "dataset_contract.json").exists()
    assert (small_cfg.data_dir / "model_meta.json").exists()
    assert (small_cfg.data_dir / "model_selection.json").exists()
    assert (small_cfg.reports_dir / "dq_report.md").exists()
    assert report_path.exists()
    for name in (
        "calibration_curve",
        "permutation_importance",
        "business_cost_curve",
        "precision_recall_curve",
        "decision_curve",
        "eda_churn_profile",
    ):
        assert (small_cfg.reports_dir / "figures" / f"{name}.html").exists(), name
        assert (small_cfg.reports_dir / "figures" / f"{name}.json").exists(), name

    metrics = json.loads((small_cfg.reports_dir / "metrics.json").read_text())
    expected = {
        "naive_majority",
        "logreg_threshold_0.5",
        "selected_model",
        "selected_model_calibrated",
    }
    assert expected <= set(metrics), set(metrics)
    tuned = [
        k for k in metrics if k.startswith("logreg_threshold_") and k != "logreg_threshold_0.5"
    ]
    assert len(tuned) == 1, "exactly one tuned logreg row"
    for name, run in metrics.items():
        if name.startswith("_"):
            continue  # metadata block, not a run
        assert {"roc_auc", "f1_macro", "business_cost"} <= set(run)
    for run in ("selected_model", "selected_model_calibrated"):
        assert "ece" in metrics[run], "ECE reported for selected runs"
    ci = metrics["_meta"]["cost_delta_ci"]
    assert ci["n_boot"] == 2000 and ci["lo"] <= ci["point"] <= ci["hi"]
    assert (small_cfg.reports_dir / "figures" / "bootstrap_ci.json").exists()
    selected_cost = metrics["selected_model"]["business_cost"]
    naive_cost = metrics["naive_majority"]["business_cost"]
    assert selected_cost <= naive_cost, "selected model should not lose to naive"

    # HPO persisted its selection into the isolated params file
    prod = params_file.read_text()
    assert "model_family" in prod


def test_dq_gate_catches_nan_missingness(
    small_cfg: ChurnConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NaN-encoded gaps count as missing: 10% NaN age must trip the gate."""
    import churn_pipeline.cli as cli
    import numpy as np
    import polars as pl

    n = 100
    bad = pl.DataFrame(
        {
            "age": [np.nan] * 10 + [40.0] * 90,
            "tenure_months": [12.0] * n,
            "monthly_charges": [70.0] * n,
            "support_calls": [1.0] * n,
            "contract": ["one-year"] * n,
            "churned": [0, 1] * 50,
        }
    )
    with pytest.raises(Exception) as exc_info:
        cli.run_dq_gates(bad)
    report = exc_info.value.report  # DQGateError carries the failing report
    age_check = next(c for c in report.checks if c.name == "null_rate" and c.column == "age")
    assert not age_check.passed and abs((age_check.metric or 0.0) - 0.1) < 1e-9

    import portfolio_core.synthetic as synthetic_module

    monkeypatch.setattr(synthetic_module, "churn", lambda seed, n: bad)
    with pytest.raises(Exception, match="DQ gates failed"):
        cli.prepare_core(small_cfg)


def test_dq_gate_failure_raises(small_cfg: ChurnConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    """A null rate above the gate limit must halt the pipeline loudly."""
    import churn_pipeline.cli as cli
    import polars as pl
    import portfolio_core.synthetic as synthetic_module

    broken = pl.DataFrame(
        {
            "age": [None] * 10,
            "tenure_months": [1.0] * 10,
            "monthly_charges": [50.0] * 10,
            "support_calls": [0.0] * 10,
            "contract": ["one-year"] * 10,
            "churned": [0, 1] * 5,
        }
    )
    monkeypatch.setattr(synthetic_module, "churn", lambda seed, n: broken)
    with pytest.raises(Exception, match="DQ gates failed"):
        cli.prepare_core(small_cfg)


def test_sensitivity_reuses_baseline_artifacts(small_cfg: ChurnConfig, params_file: Path) -> None:
    """What-if variants re-score the persisted pipeline; the production-fn_cost
    variant must reproduce the baseline costs, and metrics.json must not move."""
    from churn_pipeline.cli import sensitivity_core

    prepare_core(small_cfg)
    train_core(small_cfg, params_file=params_file)
    evaluate_core(small_cfg)
    metrics_before = (small_cfg.reports_dir / "metrics.json").read_text()

    out = sensitivity_core(small_cfg, fn_costs=[float(small_cfg.fn_cost), 8.0])
    data = json.loads(out.read_text())

    assert data["baseline_fn_cost"] == float(small_cfg.fn_cost)
    keys = list(data["variants"])
    assert len(keys) == 2 and keys[0].startswith("fn") and keys[1].startswith("fn")
    prod_key = f"fn{small_cfg.fn_cost:g}"
    assert data["variants"][prod_key]["matches_baseline"]
    for variant in data["variants"].values():
        assert variant["naive_cost"] > 0
        assert variant["calibrated_cost"] > 0
        assert 0.0 <= variant["calibrated_opt"] <= 1.0
        ci = variant["cost_delta_ci"]
        assert ci["lo"] <= ci["point"] <= ci["hi"]
    # the baseline artifact is untouched by the what-if pass
    assert (small_cfg.reports_dir / "metrics.json").read_text() == metrics_before
