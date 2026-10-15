"""HPO search-space and determinism tests (toy studies, no network)."""

import numpy as np
import pandas as pd
import pytest
from churn_pipeline.config import ChurnConfig
from churn_pipeline.hpo import (
    MODEL_FAMILIES,
    build_estimator,
    run_study,
    suggest_params,
)
from optuna.trial import FixedTrial


def test_search_space_bounds_logreg() -> None:
    trial = FixedTrial({"model": "logreg", "C": 1e-3, "l1_ratio": 1.0})
    family, params = suggest_params(trial)
    assert family == "logreg"
    assert 1e-3 <= params["C"] <= 1e2
    assert 0.0 <= params["l1_ratio"] <= 1.0


def test_search_space_bounds_histgb() -> None:
    trial = FixedTrial(
        {
            "model": "histgb",
            "learning_rate": 0.3,
            "max_iter": 150,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 60,
        }
    )
    family, params = suggest_params(trial)
    assert family == "histgb"
    assert 0.05 <= params["learning_rate"] <= 0.3
    assert 50 <= params["max_iter"] <= 150
    assert 15 <= params["max_leaf_nodes"] <= 31
    assert 20 <= params["min_samples_leaf"] <= 60


def test_search_space_bounds_xgboost() -> None:
    trial = FixedTrial(
        {
            "model": "xgboost",
            "n_estimators": 300,
            "learning_rate": 0.3,
            "max_depth": 8,
            "subsample": 1.0,
        }
    )
    family, params = suggest_params(trial)
    assert family == "xgboost"
    assert 50 <= params["n_estimators"] <= 300
    assert 0.03 <= params["learning_rate"] <= 0.3
    assert 3 <= params["max_depth"] <= 8
    assert 0.5 <= params["subsample"] <= 1.0


def test_search_space_bounds_lightgbm() -> None:
    trial = FixedTrial(
        {
            "model": "lightgbm",
            "n_estimators": 50,
            "learning_rate": 0.03,
            "num_leaves": 63,
            "min_child_samples": 60,
        }
    )
    family, params = suggest_params(trial)
    assert family == "lightgbm"
    assert 50 <= params["n_estimators"] <= 300
    assert 0.03 <= params["learning_rate"] <= 0.3
    assert 15 <= params["num_leaves"] <= 63
    assert 20 <= params["min_child_samples"] <= 60


def test_search_space_families() -> None:
    assert set(MODEL_FAMILIES) == {"logreg", "histgb", "xgboost", "lightgbm"}


def test_build_estimator_unknown_family(small_cfg: ChurnConfig) -> None:
    with pytest.raises(ValueError, match="unknown model family"):
        build_estimator(small_cfg, "not-a-family", {})


def test_build_estimator_resolves_solver_from_l1_ratio(small_cfg: ChurnConfig) -> None:
    l2 = build_estimator(small_cfg, "logreg", {"C": 1.0, "l1_ratio": 0.0}).named_steps["clf"]
    assert l2.solver == "lbfgs"
    elastic = build_estimator(small_cfg, "logreg", {"C": 1.0, "l1_ratio": 0.5}).named_steps["clf"]
    assert elastic.solver == "saga"
    assert elastic.l1_ratio == 0.5


def test_boosting_arms_fit_inside_pipeline(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame
) -> None:
    """XGB/LGBM arms keep the pipeline contract: fit on raw messy frame."""
    from churn_pipeline.model import build_pipeline

    X = tiny_synthetic[["age", "tenure_months", "monthly_charges", "support_calls", "contract"]]
    y = tiny_synthetic["churned"].astype(int)
    for family, params in (
        ("xgboost", {"n_estimators": 20, "learning_rate": 0.2, "max_depth": 3, "subsample": 0.8}),
        (
            "lightgbm",
            {"n_estimators": 20, "learning_rate": 0.2, "num_leaves": 15, "min_child_samples": 20},
        ),
    ):
        pipe = build_pipeline(small_cfg, family=family, params=params)
        pipe.fit(X, y)
        proba = pipe.predict_proba(X)
        assert proba.shape == (len(X), 2)
        assert np.isfinite(proba).all(), family


def _toy_xy() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(0)
    n = 200
    charges = rng.normal(70, 25, n)
    contract = rng.choice(["month-to-month", "one-year", "two-year"], n)
    logit = -3.5 + 0.04 * (charges - 70) + np.where(contract == "month-to-month", 1.4, 0)
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    X = pd.DataFrame(
        {
            "age": rng.normal(45, 12, n),
            "tenure_months": rng.exponential(24, n),
            "monthly_charges": charges,
            "support_calls": rng.poisson(1.2, n).astype(float),
            "contract": contract,
        }
    )
    return X, pd.Series(y)


def test_selection_deterministic_on_toy_study(small_cfg: ChurnConfig) -> None:
    """Same seed + data → same selected family and params."""
    X, y = _toy_xy()
    s1 = run_study(small_cfg, X, y, n_trials=6)
    s2 = run_study(small_cfg, X, y, n_trials=6)
    assert s1.family == s2.family
    assert s1.params == s2.params
    assert s1.n_trials == 6
    assert s1.objective == small_cfg.hpo_objective == "cost"
    assert set(s1.family_scores) == set(MODEL_FAMILIES)
