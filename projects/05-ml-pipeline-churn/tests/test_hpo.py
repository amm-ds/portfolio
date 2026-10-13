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


def test_search_space_families() -> None:
    assert set(MODEL_FAMILIES) == {"logreg", "histgb"}


def test_build_estimator_unknown_family(small_cfg: ChurnConfig) -> None:
    with pytest.raises(ValueError, match="unknown model family"):
        build_estimator(small_cfg, "xgboost", {})


def test_build_estimator_resolves_solver_from_l1_ratio(small_cfg: ChurnConfig) -> None:
    l2 = build_estimator(small_cfg, "logreg", {"C": 1.0, "l1_ratio": 0.0}).named_steps["clf"]
    assert l2.solver == "lbfgs"
    elastic = build_estimator(small_cfg, "logreg", {"C": 1.0, "l1_ratio": 0.5}).named_steps["clf"]
    assert elastic.solver == "saga"
    assert elastic.l1_ratio == 0.5


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
    assert set(s1.family_scores) == set(MODEL_FAMILIES)
