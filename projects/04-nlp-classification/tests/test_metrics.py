"""Metrics sanity tests via the platform's classification_metrics."""

from nlp_classification.evaluate import run_result
from portfolio_eval.metrics import RunResult, compare_runs
from portfolio_eval.ml import classification_metrics


def test_classification_metrics_perfect_predictions() -> None:
    y = [0, 1, 2, 3, 0, 1, 2, 3]
    results = {m.name: m.value for m in classification_metrics(y, y)}
    assert results["accuracy"] == 1.0
    assert results["f1_macro"] == 1.0
    assert results["precision_macro"] == 1.0
    assert results["recall_macro"] == 1.0


def test_classification_metrics_all_wrong() -> None:
    y_true = [0, 0, 1, 1]
    y_pred = [1, 1, 0, 0]
    results = {m.name: m.value for m in classification_metrics(y_true, y_pred)}
    assert results["f1_macro"] == 0.0
    assert results["accuracy"] == 0.0


def test_run_result_includes_weighted_f1() -> None:
    run = run_result("test", [0, 1, 2, 3], [0, 1, 2, 2])
    names = {m.name for m in run.metrics}
    assert {"accuracy", "f1_macro", "f1_weighted"} <= names
    assert 0.0 < run.get("f1_weighted").value < 1.0  # type: ignore[union-attr]


def test_compare_runs_ranks_best_first() -> None:
    good = RunResult("good", classification_metrics([0, 1], [0, 1]))
    bad = RunResult("bad", classification_metrics([0, 1], [1, 0]))
    ranking = compare_runs([bad, good], "f1_macro")
    assert ranking["ranking"] == ["good", "bad"]
