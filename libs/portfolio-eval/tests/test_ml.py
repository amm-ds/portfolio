import pytest
from portfolio_eval.metrics import MetricResult, RunResult, compare_runs
from portfolio_eval.ml import RunComparison, classification_metrics, regression_metrics


def test_classification_metrics_perfect() -> None:
    m = classification_metrics([0, 1, 2, 0], [0, 1, 2, 0])
    d = {x.name: x.value for x in m}
    assert d["accuracy"] == 1.0 and d["f1_macro"] == 1.0


def test_regression_metrics_values() -> None:
    m = regression_metrics([1.0, 2.0, 3.0], [1.0, 2.0, 4.0])
    d = {x.name: x.value for x in m}
    assert d["mae"] == pytest.approx(1 / 3)
    assert d["rmse"] == pytest.approx((1 / 3) ** 0.5)
    assert d["mape_pct"] == pytest.approx((0 + 0 + 1 / 3) / 3 * 100)


def test_compare_runs_ranking_respects_higher_is_better() -> None:
    good = RunResult("good", [MetricResult("f1", 0.9)])
    bad = RunResult("bad", [MetricResult("f1", 0.5, higher_is_better=False)])
    out = compare_runs([bad, good], "f1")
    assert out["ranking"] == ["good", "bad"]


def test_run_comparison_markdown_and_figure() -> None:
    rc = RunComparison([RunResult("m1", [MetricResult("mae", 1.0, higher_is_better=False)])])
    md = rc.to_markdown()
    assert "| run | mae |" in md and "| m1 | 1.0000 |" in md
    fig = rc.figure()
    assert len(fig.data) == 1
