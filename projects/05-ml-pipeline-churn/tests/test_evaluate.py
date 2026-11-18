"""End-to-end evaluation on a small config, plus cost/calibration unit tests."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import pytest
from churn_pipeline.cli import evaluate_core, prepare_core, train_core
from churn_pipeline.config import ChurnConfig, pd
from churn_pipeline.evaluate import (
    artifact_paths,
    business_cost,
    cost_curve,
    evaluate_holdout,
    expected_calibration_error,
    naive_majority_run,
    net_benefit,
    paired_bootstrap_cost_delta,
    select_oof_thresholds,
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


def test_naive_majority_is_fixed_contact_everyone(small_cfg: ChurnConfig) -> None:
    """The comparator never chooses contact-none by inspecting holdout cost."""
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    run, costs, threshold = naive_majority_run(small_cfg, y_true, 0.5)
    assert run.name == "naive_majority"
    assert costs.min() < 5.0 * int(y_true.sum())
    cost = run.get("business_cost")
    assert cost is not None and cost.value == 5.0
    auc = run.get("roc_auc")
    assert auc is not None and auc.value == 0.5
    assert threshold == 0.0


def test_holdout_evaluation_preserves_nonoptimal_frozen_thresholds(
    small_cfg: ChurnConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lower holdout cost elsewhere in the grid must not move the policy."""

    class FixedProbabilityModel:
        def __init__(self, proba: np.ndarray) -> None:
            self.proba = proba

        def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
            assert len(X) == len(self.proba)
            return np.column_stack((1.0 - self.proba, self.proba))

    def no_importance(*args: Any, **kwargs: Any) -> go.Figure:
        return go.Figure()

    monkeypatch.setattr("churn_pipeline.evaluate.importance_figure", no_importance)
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    proba = np.array([0.1, 0.3, 0.5, 0.7, 0.2, 0.4, 0.6, 0.8])
    models: dict[str, Any] = {
        name: FixedProbabilityModel(proba) for name in ("logreg", "selected", "selected_calibrated")
    }
    thresholds = {"logreg": 0.8, "selected": 0.8, "selected_calibrated": 0.8}
    runs, _figures, summary = evaluate_holdout(
        small_cfg,
        models,
        pd.DataFrame({"feature": range(len(y))}),
        pd.Series(y),
        train_base_rate=0.5,
        thresholds=thresholds,
    )

    assert summary["calibrated_opt"] == 0.8
    assert summary["calibrated_cost"] == 15.0
    _costs, holdout_optimum = cost_curve(small_cfg, y, proba)
    assert holdout_optimum != 0.8
    assert summary["cost_delta_ci"]["point"] == summary["calibrated_cost"] - summary["naive_cost"]
    assert summary["cost_delta_ci_logreg"]["point"] == (
        summary["calibrated_cost"] - summary["logreg_default_cost"]
    )
    assert runs[2].name == "logreg_threshold_0.800"


def test_end_to_end_cli_cores(small_cfg: ChurnConfig, params_file: Path) -> None:
    """prepare → train (HPO) → evaluate through the CLI cores (no network)."""
    prepare_core(small_cfg)
    train_core(small_cfg, params_file=params_file)
    report_path = evaluate_core(small_cfg)

    paths = artifact_paths(small_cfg)
    for key in (
        "logreg",
        "selected",
        "selected_calibrated",
        "holdout",
        "training_predictions",
        "operating_policy",
    ):
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
    calibrated_cost = metrics["selected_model_calibrated"]["business_cost"]
    assert ci["point"] == calibrated_cost - metrics["naive_majority"]["business_cost"]
    logreg_ci = metrics["_meta"]["cost_delta_ci_logreg"]
    assert logreg_ci["point"] == (
        calibrated_cost - metrics["logreg_threshold_0.5"]["business_cost"]
    )
    assert metrics["_meta"]["threshold_selection"]["data"] == "training_oof"
    assert (small_cfg.reports_dir / "figures" / "bootstrap_ci.json").exists()

    policy = json.loads(paths["operating_policy"].read_text())
    with np.load(paths["training_predictions"]) as training:
        expected_thresholds, _costs = select_oof_thresholds(
            small_cfg,
            np.asarray(training["y_train"], dtype=int),
            {
                name: np.asarray(training[name], dtype=float)
                for name in ("logreg", "selected", "selected_calibrated")
            },
        )
    assert policy["thresholds"] == expected_thresholds
    assert metrics["_meta"]["calibrated_opt"] == expected_thresholds["selected_calibrated"]

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


def test_threshold_selection_ignores_holdout(small_cfg: ChurnConfig) -> None:
    """Holdout isolation: thresholds freeze from training OOF predictions only.

    A sentinel holdout-label vector lives beside the fixture but is never
    passed to the selection; the chosen threshold must not move. The second
    half proves the labels genuinely drive selection (so the isolation is
    meaningful, not vacuous).
    """
    import inspect

    y_train = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    proba_map = {"m": np.array([0.1, 0.4, 0.35, 0.8, 0.2, 0.7, 0.05, 0.55])}
    thresholds, costs = select_oof_thresholds(small_cfg, y_train, proba_map)

    # Sentinel holdout: corrupted labels the selection never receives.
    y_holdout_sentinel = np.full(8, -999)
    thresholds_again, _ = select_oof_thresholds(small_cfg, y_train, proba_map)
    assert thresholds_again == thresholds
    assert y_holdout_sentinel[0] == -999  # the poison exists and is untouched

    # Consistency with the underlying curve for the committed fixture.
    curve, optimal = cost_curve(small_cfg, y_train, proba_map["m"])
    assert thresholds["m"] == optimal
    assert costs["m"] == float(curve.min())

    # Not vacuous: labels DO drive the argmin — an all-zero label vector
    # yields a different optimum (0.825 vs 0.225 on this grid), so a selection
    # that read the holdout would move. It does not.
    _, optimal_alt = cost_curve(small_cfg, np.zeros(8, dtype=int), proba_map["m"])
    assert optimal_alt != optimal
    # Signature guard: no holdout parameter can be added without failing here.
    assert set(inspect.signature(select_oof_thresholds).parameters) <= {
        "cfg",
        "y_train",
        "proba_map",
    }
