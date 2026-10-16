"""Qini computation exactness: hand-calculated curves, coefficients, profits."""

import numpy as np
import pytest
from uplift_experimentation.qini import (
    incremental_at_full,
    profit_curve,
    qini_coefficient,
    qini_points,
    trapezoid,
    uplift_by_decile,
)


def test_qini_points_exact_hand_calculation() -> None:
    # 4 customers ordered by score: (t,y) = (1,1), (0,0), (1,0), (0,1).
    treatment = np.array([1, 0, 1, 0])
    outcome = np.array([1, 0, 0, 1])
    score = np.array([0.9, 0.8, 0.7, 0.6])
    fractions, inc = qini_points(treatment, outcome, score)
    assert np.allclose(fractions, [0.0, 0.25, 0.5, 0.75, 1.0])
    # Empty-slice convention (see qini_points docstring):
    # k=1: treated only -> 1 * (1/1 - 0) = 1
    # k=2: nt=1, nc=1 -> 1 * (1 - 0) = 1
    # k=3: nt=2, nc=1 -> 2 * (0.5 - 0) = 1
    # k=4: nt=2, nc=2 -> 2 * (0.5 - 0.5) = 0
    assert np.allclose(inc, [0.0, 1.0, 1.0, 1.0, 0.0])


def test_qini_coefficient_exact_for_perfect_ranking() -> None:
    # Treated responders both rank first, so every slice's contrast is maximal.
    treatment = np.array([1, 1, 0, 0])
    outcome = np.array([1, 1, 0, 0])
    score = np.array([0.9, 0.8, 0.7, 0.6])
    fractions, inc = qini_points(treatment, outcome, score)
    assert np.allclose(inc, [0.0, 1.0, 2.0, 2.0, 2.0])
    area_model = trapezoid(fractions, inc)
    inc[-1] / 2.0  # = 1.0
    assert qini_coefficient(treatment, outcome, score) == pytest.approx(area_model - 1.0)
    assert qini_coefficient(treatment, outcome, score) == pytest.approx(0.5)


def test_qini_coefficient_centered_at_zero_for_constant_scores() -> None:
    # A constant score is one arbitrary ordering; its coefficient fluctuates
    # around the random line's area with sd ~ O(n_t * sd(rate diff)). Over many
    # replications the mean must be ~0 — the random baseline is unbiased.
    rng = np.random.default_rng(123)
    coefficients = []
    for _ in range(200):
        n = 2_000
        treatment = rng.integers(0, 2, n)
        outcome = rng.binomial(1, 0.05, n)
        coefficients.append(qini_coefficient(treatment, outcome, np.ones(n)))
    assert abs(float(np.mean(coefficients))) < 1.0


def test_incremental_at_full_is_difference_in_means_scaled() -> None:
    treatment = np.array([1, 1, 0, 0])
    outcome = np.array([1, 0, 0, 0])
    # p_t = 0.5, p_c = 0.0, n_t = 2 -> incremental = 2 * 0.5 = 1
    assert incremental_at_full(treatment, outcome) == pytest.approx(1.0)


def test_profit_curve_cost_math() -> None:
    # 1,000 customers, 25% targeted, 1 incremental conversion, margin $150, $0.01/email:
    # profit = 1 * 150 - 250 * 0.01 = 147.5
    profit = profit_curve(
        fractions=np.array([0.25]),
        incremental=np.array([1.0]),
        n_total=1000,
        margin=150.0,
        cost_per_email=0.01,
    )
    assert profit[0] == pytest.approx(147.5)
    # No incremental conversions: pure mailing cost.
    loss = profit_curve(
        fractions=np.array([1.0]),
        incremental=np.array([0.0]),
        n_total=1000,
        margin=150.0,
        cost_per_email=0.01,
    )
    assert loss[0] == pytest.approx(-10.0)


def test_trapezoid_exact() -> None:
    x = np.array([0.0, 0.5, 1.0])
    y = np.array([0.0, 1.0, 0.0])
    assert trapezoid(x, y) == pytest.approx(0.5)


def test_uplift_by_decile_counts_and_empirical() -> None:
    # 20 rows, 2 deciles; scores 0..19 so the top decile is rows 10..19.
    # Treated in the top decile are the even rows there; they all convert, the
    # control rows do not -> empirical uplift of decile 1 is exactly 1.0.
    # Row 0 is a treated non-converter so decile 2 is an all-zero contrast.
    n = 20
    score = np.arange(n, dtype=float)
    treatment = np.array([1 if (i == 0 or (10 <= i < 20 and i % 2 == 0)) else 0 for i in range(n)])
    outcome = np.where(np.arange(n) == 0, 0.0, treatment.astype(float))
    table = uplift_by_decile(treatment, outcome, score, n_deciles=2)
    assert table["n_treated"][0] == 5 and table["n_control"][0] == 5
    assert table["n_treated"][1] == 1 and table["n_control"][1] == 9
    assert table["empirical_uplift"][0] == pytest.approx(1.0)
    assert table["empirical_uplift"][1] == pytest.approx(0.0)
    assert table["mean_score"][0] > table["mean_score"][1]  # decile 1 = highest scores
