"""Correctness tests for observed-outcome multi-arm DR/IPW policy values."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from uplift_experimentation.evaluate import write_metrics_json
from uplift_experimentation.models import cross_fit_outcome_models
from uplift_experimentation.policy_value import (
    ACTIONS,
    VALUE_POLICIES,
    build_policy_probabilities,
    dr_ipw_contributions,
    policy_value_read,
)


def test_dr_ipw_hand_calculation() -> None:
    assignment = np.array([0, 1, 2, 0])
    outcome = np.array([1.0, 0.0, 1.0, 0.0])
    mu = np.array(
        [
            [0.4, 0.1, 0.2],
            [0.3, 0.5, 0.1],
            [0.2, 0.4, 0.6],
            [0.7, 0.2, 0.3],
        ]
    )
    pi = np.zeros((4, 3))
    pi[:, 0] = 1.0  # everyone receives Mens

    dr, ipw = dr_ipw_contributions(assignment, outcome, mu, pi, propensities=0.5)

    np.testing.assert_allclose(dr, [1.6, 0.3, 0.2, -0.7])
    np.testing.assert_allclose(ipw, [2.0, 0.0, 0.0, 0.0])
    assert dr.mean() == pytest.approx(0.35)
    assert ipw.mean() == pytest.approx(0.5)


def test_stochastic_policy_uses_policy_probability_in_ipw_correction() -> None:
    assignment = np.array([0, 1, 2])
    outcome = np.array([1.0, 1.0, 1.0])
    mu = np.zeros((3, 3))
    pi = np.full((3, 3), 0.25)
    _dr, ipw = dr_ipw_contributions(assignment, outcome, mu, pi, propensities=0.5)
    np.testing.assert_allclose(ipw, 0.5)


def test_policy_probabilities_exact_budget_and_stochastic_random() -> None:
    u_m = np.array([0.5, 0.4, -0.1, 0.2])
    u_w = np.array([0.1, 0.6, 0.3, 0.2])
    probs = build_policy_probabilities(u_m, u_w, budget=0.5)

    assert set(probs) == set(VALUE_POLICIES)
    for values in probs.values():
        assert values.shape == (4, len(ACTIONS))
        np.testing.assert_allclose(values.sum(axis=1), 1.0)
        assert (values >= 0.0).all()
    # Best-arm: row 1 -> Womens and row 0 -> Mens; tied row 3 and negative
    # row 2 remain control. Single-arm: rows 0 and 1 -> Mens.
    np.testing.assert_array_equal(probs["best_arm"].argmax(axis=1), [0, 1, 2, 2])
    np.testing.assert_array_equal(probs["single_arm"].argmax(axis=1), [0, 0, 2, 2])
    # Random is stochastic, including its none/control mass.
    np.testing.assert_allclose(probs["random"][0], [0.5, 0.0, 0.5])
    np.testing.assert_allclose(probs["random"][1], [0.0, 0.5, 0.5])
    np.testing.assert_allclose(probs["random"][2], [0.0, 0.5, 0.5])
    np.testing.assert_allclose(probs["random"][3], [0.0, 0.0, 1.0])
    assert np.isclose(1.0 - probs["best_arm"][:, 2].mean(), 0.5)


def _scored_frame(n: int = 600, seed: int = 19) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    segment = rng.choice(["Mens E-Mail", "Womens E-Mail", "No E-Mail"], n)
    assignment = np.select(
        [segment == "Mens E-Mail", segment == "Womens E-Mail"], [0, 1], default=2
    )
    x = rng.random(n)
    rates = np.column_stack([0.05 + 0.10 * x, 0.05 + 0.05 * x, np.full(n, 0.05)])
    y = rng.binomial(1, rates[np.arange(n), assignment]).astype(float)
    return pd.DataFrame(
        {
            "segment": segment,
            "conversion": y,
            "uplift_mens": 0.10 * x - 0.02,
            "uplift_womens": 0.05 * x - 0.01,
            "mu_mens": rates[:, 0],
            "mu_womens": rates[:, 1],
            "mu_control": rates[:, 2],
        }
    )


def test_policy_value_read_paired_intervals_and_determinism() -> None:
    df = _scored_frame()
    kwargs = {
        "budget": 0.25,
        "revenue_per_conversion": 114.0,
        "cost_per_email": 0.01,
        "n_boot": 100,
        "seed": 99,
        "cv_folds": 5,
    }
    first = policy_value_read(df, **kwargs)
    second = policy_value_read(df, **kwargs)

    assert first == second
    assert set(first["policies"]) == set(VALUE_POLICIES)
    assert "known randomized assignment" in first["propensity"]
    for read in first["policies"].values():
        assert 0.0 <= read["mailed_fraction"] <= 1.0
        for estimator in ("dr", "ipw"):
            values = read[estimator]
            assert np.isfinite(values["conversion_rate"])
            assert values["profit_ci"][0] <= values["profit_ci"][1]
            inc_ci = values["incremental_conversions_vs_no_email_ci"]
            assert inc_ci[0] <= inc_ci[1]
    for estimator in ("dr", "ipw"):
        no_email = first["policies"]["no_email"][estimator]
        assert no_email["incremental_conversions_vs_no_email"] == 0.0
        assert no_email["profit"] == 0.0
        assert no_email["profit_ci"] == [0.0, 0.0]
    pair = first["pairs"]["best_arm - single_arm"]
    for estimator in ("dr", "ipw"):
        ci = pair[estimator]["profit_diff_ci"]
        assert pair[estimator]["spans_zero"] == (ci[0] <= 0.0 <= ci[1])


def test_cross_fit_outcome_models_shape_and_determinism() -> None:
    rng = np.random.default_rng(23)
    n = 600
    X = pd.DataFrame(
        {
            "recency": rng.integers(1, 13, n).astype(float),
            "history": rng.gamma(2.0, 60.0, n),
            "log_history": np.zeros(n),
            "mens": rng.integers(0, 2, n).astype(float),
            "womens": rng.integers(0, 2, n).astype(float),
            "newbie": rng.integers(0, 2, n).astype(float),
            "channel": rng.choice(["Phone", "Web", "Multichannel"], n),
            "zip_code": rng.choice(["Surburban", "Urban", "Rural"], n),
        }
    )
    X["log_history"] = np.log1p(X["history"])
    assignment = rng.integers(0, 3, n)
    y = rng.binomial(1, 0.05 + 0.10 * (assignment == 0) + 0.05 * (assignment == 1))

    first = cross_fit_outcome_models(X, assignment, y, folds=3, seed=7)
    second = cross_fit_outcome_models(X, assignment, y, folds=3, seed=7)

    assert list(first.columns) == ["mu_mens", "mu_womens", "mu_control"]
    assert first.shape == (n, 3)
    assert np.isfinite(first.to_numpy()).all()
    assert ((first.to_numpy() > 0.0) & (first.to_numpy() < 1.0)).all()
    pd.testing.assert_frame_equal(first, second)


def test_metrics_json_uses_null_for_non_finite_values(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    write_metrics_json({"treat-everyone": {"profit_at_budget": float("nan")}, "finite": 1.0}, path)

    raw = path.read_text()
    loaded = json.loads(raw)
    assert loaded["treat-everyone"]["profit_at_budget"] is None
    assert loaded["finite"] == 1.0
    assert "NaN" not in raw and "Infinity" not in raw
