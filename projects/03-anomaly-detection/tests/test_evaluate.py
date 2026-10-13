"""Evaluator tests: perfect separation scores AUC 1.0, ranking helpers, artifacts."""

import json
from pathlib import Path

import numpy as np
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.evaluate import (
    add_random_baseline,
    best_model,
    eda_signals_overview,
    evaluate_scores,
    predict_at_contamination,
    random_scores,
    roc_figure,
    run_evaluation,
)


def test_perfectly_separable_scores_score_1() -> None:
    """AUC must be exactly 1.0 when every anomaly outranks every normal point."""
    y_true = np.array([0] * 50 + [1] * 10)
    scores = np.array([0.01 * i for i in range(50)] + [10.0 + i for i in range(10)])
    run = evaluate_scores("fixture", y_true, scores)
    roc = run.get("roc_auc")
    pr = run.get("pr_auc")
    assert roc is not None and pr is not None
    assert roc.value == pytest.approx(1.0)
    assert pr.value == pytest.approx(1.0)
    assert roc.split == "test"


def test_inverted_scores_score_0() -> None:
    y_true = np.array([0, 0, 1, 1])
    scores = np.array([1.0, 0.9, 0.1, 0.0])
    run = evaluate_scores("fixture", y_true, scores)
    assert run.get("roc_auc").value == pytest.approx(0.0)  # type: ignore[union-attr]


def test_predict_at_contamination_flags_top_fraction() -> None:
    scores = np.arange(100, dtype=float)
    flags = predict_at_contamination(scores, 0.1)
    assert flags.sum() == 10
    assert flags[-10:].all()
    assert not flags[:90].any()


def test_random_baseline_is_seeded_and_at_chance(small_config: AnomalyConfig) -> None:
    """Seeded random scores: reproducible, AUC ≈ 0.5, PR-AUC ≈ prevalence."""
    from anomaly_detection.data import generate

    y_true = generate(small_config)["is_anomaly"].to_numpy().astype(int)
    a = random_scores(len(y_true), small_config.seed)
    b = random_scores(len(y_true), small_config.seed)
    np.testing.assert_array_equal(a, b)
    run = evaluate_scores("random", y_true, a)
    roc = run.get("roc_auc")
    pr = run.get("pr_auc")
    assert roc is not None and pr is not None
    assert roc.value == pytest.approx(0.5, abs=0.1)
    assert pr.value == pytest.approx(y_true.mean(), abs=0.05)


def test_random_baseline_appears_first_in_overlays(small_config: AnomalyConfig) -> None:
    """The baseline run leads the run order and shows up in the ROC overlay."""
    from anomaly_detection.data import generate

    y_true = generate(small_config)["is_anomaly"].to_numpy().astype(int)
    runs: list = []
    scores_by_model: dict[str, np.ndarray] = {}
    add_random_baseline(runs, scores_by_model, y_test=y_true, config=small_config)
    assert runs[0].name == "random"
    fig = roc_figure(runs, scores_by_model, y_true)
    names = [t.name for t in fig.data]
    assert any(n and n.startswith("random") for n in names)


def test_eda_signals_overview_marks_injected_anomalies(
    small_config: AnomalyConfig,
) -> None:
    from anomaly_detection.data import generate

    fig = eda_signals_overview(generate(small_config))
    names = [t.name for t in fig.data]
    assert names[:3] == ["cpu", "mem", "latency_ms"]
    assert "injected anomaly" in names
    marker = next(t for t in fig.data if t.name == "injected anomaly")
    assert len(marker.x) > 0


def test_score_distribution_figure_separates_masses(small_config: AnomalyConfig) -> None:
    """Histogram shows normal vs. anomaly masses with a log-y axis."""
    from anomaly_detection.evaluate import score_distribution_figure, threshold_sweep_figure

    rng = np.random.default_rng(0)
    y_true = np.array([0] * 200 + [1] * 40)
    scores = np.concatenate([rng.normal(0.0, 0.3, 200), rng.normal(3.0, 0.5, 40)])
    fig = score_distribution_figure(scores, y_true, small_config, "fixture")
    names = [t.name for t in fig.data]
    assert "normal" in names and "anomaly (injected)" in names
    assert fig.layout.yaxis.type == "log"
    sweep = threshold_sweep_figure(scores, y_true, small_config, "fixture")
    sweep_names = [t.name for t in sweep.data]
    assert "recall (TPR)" in sweep_names and "precision" in sweep_names


def test_best_model_by_pr_auc() -> None:
    good = evaluate_scores("good", np.array([0, 1]), np.array([0.0, 1.0]))
    bad = evaluate_scores("bad", np.array([0, 1]), np.array([1.0, 0.0]))
    assert best_model([good, bad]) == "good"
    with pytest.raises(ValueError):
        best_model([])


def test_run_evaluation_writes_artifacts(small_config: AnomalyConfig, tmp_path: Path) -> None:
    from anomaly_detection.data import prepare
    from anomaly_detection.features import build_features, save_features
    from anomaly_detection.hpo import tune_all
    from anomaly_detection.model import (
        feature_matrix,
        fit_models,
        save_models,
        split_train_test,
    )

    config = AnomalyConfig(
        n=2_000,
        hpo_trials=5,
        data_dir=str(tmp_path / "d"),
        reports_dir=str(tmp_path / "r"),
    )
    df = prepare(config)
    save_features(build_features(df, config.windows), config)
    feat = build_features(df, config.windows)
    train, _ = split_train_test(feat, config.train_frac)
    x_train = feature_matrix(train, config)
    save_models(fit_models(x_train, config), config)
    tune_all(config, x_train, train["is_anomaly"].to_numpy().astype(int))

    metrics, report_path = run_evaluation(config)
    assert set(metrics) == {
        "random",
        "isolation_forest",
        "lof",
        "ocsvm",
        "isolation_forest_tuned",
        "lof_tuned",
        "ocsvm_tuned",
    }
    for values in metrics.values():
        assert set(values) == {"roc_auc", "pr_auc"}
        assert 0.0 <= values["roc_auc"] <= 1.0
    # random reference sits at chance; detectors must beat it on AUC
    assert metrics["random"]["roc_auc"] == pytest.approx(0.5, abs=0.1)
    assert metrics["isolation_forest"]["roc_auc"] > metrics["random"]["roc_auc"]
    assert report_path.exists()
    assert (config.eval_dir / "metrics.json").exists()
    assert json.loads((config.eval_dir / "metrics.json").read_text()) == metrics
    for name in (
        "eda_signals_overview",
        "roc_curves",
        "pr_curves",
        "telemetry_flags",
        "threshold_sweep",
        "score_distribution",
        "hpo_importance",
    ):
        assert (config.figures_dir / f"{name}.html").exists()
        assert (config.figures_dir / f"{name}.json").exists()
