"""End-to-end evaluation on a small config, plus cost-curve unit tests."""

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import plotly.graph_objects as go
import pytest
from churn_pipeline.cli import evaluate_core, prepare_core, train_core
from churn_pipeline.config import ChurnConfig
from churn_pipeline.evaluate import (
    artifact_paths,
    business_cost,
    cost_curve,
    evaluate_holdout,
    naive_majority_run,
)
from churn_pipeline.model import split_holdout, train_model


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


def test_naive_majority_degenerates_to_constant_costs(small_cfg: ChurnConfig) -> None:
    """Constant base-rate probability: cheaper of alarm-all vs ignore-all."""
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    base_rate = 0.5
    run, costs, optimal = naive_majority_run(small_cfg, y_true, base_rate)
    assert run.name == "naive_majority"
    n_pos, n_neg = 5, 5
    alarm_all, ignore_all = 1.0 * n_neg, 5.0 * n_pos
    assert costs.min() == min(alarm_all, ignore_all)
    assert run.get("business_cost") is not None
    assert run.get("business_cost").value == costs.min()  # type: ignore[union-attr]
    assert run.get("roc_auc") is not None and run.get("roc_auc").value == 0.5  # type: ignore[union-attr]
    assert optimal in small_cfg.threshold_grid


def test_evaluate_holdout_runs_and_figures(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame
) -> None:
    X_train, X_test, y_train, y_test = split_holdout(small_cfg, tiny_synthetic)
    grid = train_model(small_cfg, X_train, y_train)
    runs, figures, optimal = evaluate_holdout(
        small_cfg, grid.best_estimator_, X_test, y_test, train_base_rate=float(y_train.mean())
    )

    assert len(runs) == 3, "naive + default-threshold + tuned-threshold runs"
    assert runs[0].name == "naive_majority"
    assert runs[1].name == "logreg_threshold_0.5"
    assert runs[2].name.startswith("logreg_threshold_")
    metric_names = {m.name for m in runs[0].metrics}
    assert {
        "roc_auc",
        "accuracy",
        "precision_macro",
        "recall_macro",
        "f1_macro",
        "business_cost",
    } <= metric_names
    cost_naive = runs[0].get("business_cost")
    cost_default = runs[1].get("business_cost")
    cost_tuned = runs[2].get("business_cost")
    assert cost_naive is not None and cost_default is not None and cost_tuned is not None
    assert cost_tuned.value <= cost_default.value, "tuned threshold never costs more"
    assert cost_tuned.value <= cost_naive.value, "model should beat the naive baseline"

    assert set(figures) == {
        "calibration_curve",
        "permutation_importance",
        "business_cost_curve",
    }
    cost_fig = figures["business_cost_curve"]
    names = [d.name or "" for d in cost_fig.data]
    assert any("naive" in n for n in names), "naive cost curve shown in the figure"
    for fig in figures.values():
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1
    assert optimal in small_cfg.threshold_grid


def test_end_to_end_cli_cores(small_cfg: ChurnConfig) -> None:
    """prepare → train → evaluate through the CLI core functions (no network)."""
    prepare_core(small_cfg)
    train_core(small_cfg)
    report_path = evaluate_core(small_cfg)

    model_path, holdout_path = artifact_paths(small_cfg)
    assert model_path.exists() and holdout_path.exists()
    assert (small_cfg.data_dir / "churn.parquet").exists()
    assert (small_cfg.data_dir / "dataset_contract.json").exists()
    assert (small_cfg.data_dir / "model_meta.json").exists()
    assert (small_cfg.reports_dir / "dq_report.md").exists()
    assert (small_cfg.reports_dir / "metrics.json").exists()
    assert report_path.exists()
    for name in (
        "calibration_curve",
        "permutation_importance",
        "business_cost_curve",
        "eda_churn_profile",
    ):
        assert (small_cfg.reports_dir / "figures" / f"{name}.html").exists()
        assert (small_cfg.reports_dir / "figures" / f"{name}.json").exists()

    holdout = pd.read_parquet(holdout_path)
    assert "churned" in holdout.columns
    metrics = report_path.with_name("metrics.json").read_text()
    assert "roc_auc" in metrics and "business_cost" in metrics
    assert "naive_majority" in metrics, "naive baseline row persisted"


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
    import churn_pipeline.cli as cli

    with pytest.raises(Exception, match="DQ gates failed"):
        cli.prepare_core(small_cfg)
