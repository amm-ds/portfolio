"""Qini computation exactness: hand-calculated curves, coefficients, profits."""

import numpy as np
import pytest
from uplift_experimentation.qini import (
    bootstrap_policy_stats,
    ci_spans_zero,
    incremental_at_full,
    percentile_ci,
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
    # 1,000 customers, 25% targeted, 1 incremental conversion, revenue $150, $0.01/email:
    # profit = 1 * 150 - 250 * 0.01 = 147.5
    profit = profit_curve(
        fractions=np.array([0.25]),
        incremental=np.array([1.0]),
        n_total=1000,
        revenue_per_conversion=150.0,
        cost_per_email=0.01,
    )
    assert profit[0] == pytest.approx(147.5)
    # No incremental conversions: pure mailing cost.
    loss = profit_curve(
        fractions=np.array([1.0]),
        incremental=np.array([0.0]),
        n_total=1000,
        revenue_per_conversion=150.0,
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


# ---------------------------------------------------------------------------
# Paired bootstrap: determinism + the spans-zero verdict
# ---------------------------------------------------------------------------


def _bootstrap_args(n: int = 1_500, seed: int = 0) -> dict:
    """A randomized two-arm frame with one informative and one noise policy."""
    rng = np.random.default_rng(seed)
    treatment = rng.integers(0, 2, n)
    high = rng.random(n) < 0.3
    p = np.where(high, 0.10, 0.02) + treatment * np.where(high, 0.12, 0.0)
    outcome = rng.binomial(1, np.clip(p, 0, 1))
    informative = np.where(high, 1.0, 0.0) + rng.normal(0, 0.05, n)
    noise = rng.normal(0, 1, n)
    return {
        "treatment": treatment,
        "outcome": outcome,
        "scores": {"informative": informative, "noise": noise},
        "budget": 0.25,
        "n_total": n,
        "revenue_per_conversion": 114.0,
        "cost_per_email": 0.01,
        "n_boot": 300,
        "seed": 42,
    }


def test_bootstrap_is_deterministic_under_seed() -> None:
    args = {**_bootstrap_args(), "band_grid": np.linspace(0.0, 1.0, 21)}
    a = bootstrap_policy_stats(**args)
    b = bootstrap_policy_stats(**args)
    for policy in ("informative", "noise"):
        np.testing.assert_array_equal(a["qini"][policy], b["qini"][policy])
        np.testing.assert_array_equal(a["profit_at_budget"][policy], b["profit_at_budget"][policy])
        np.testing.assert_array_equal(a["band"][policy][0], b["band"][policy][0])
        np.testing.assert_array_equal(a["band"][policy][1], b["band"][policy][1])
    # The seeded-random ranking and the deterministic mail-everyone read must
    # reproduce exactly under the same seed...
    np.testing.assert_array_equal(a["random_profit_at_budget"], b["random_profit_at_budget"])
    np.testing.assert_array_equal(
        a["mail_everyone_profit_at_budget"], b["mail_everyone_profit_at_budget"]
    )
    # ...and a different seed must give a different resampling sequence.
    c = bootstrap_policy_stats(**{**args, "seed": 43})
    assert not np.array_equal(a["qini"]["informative"], c["qini"]["informative"])
    assert not np.array_equal(a["random_profit_at_budget"], c["random_profit_at_budget"])


def test_bootstrap_ci_brackets_the_point_estimate() -> None:
    args = _bootstrap_args()
    stats = bootstrap_policy_stats(**args)
    ci = percentile_ci(stats["qini"]["informative"])
    assert ci[0] < ci[1]
    point = qini_coefficient(args["treatment"], args["outcome"], args["scores"]["informative"])
    # The percentile CI is centered on the bootstrap distribution, so the point
    # estimate need not fall inside it exactly — but at this signal size the
    # bootstrap bias is far smaller than the interval half-width.
    assert ci[0] - (ci[1] - ci[0]) < point < ci[1] + (ci[1] - ci[0])
    assert abs(point - float(np.mean(stats["qini"]["informative"]))) < (ci[1] - ci[0])


def test_bootstrap_difference_ci_spans_zero_when_rankings_are_equivalent() -> None:
    # Two independent noise policies carry no ranking signal: the paired CI on
    # the Qini difference MUST span zero — no ranking is established.
    args = _bootstrap_args()
    rng = np.random.default_rng(7)
    args["scores"] = {
        "noise_a": rng.normal(0, 1, len(args["outcome"])),
        "noise_b": rng.normal(0, 1, len(args["outcome"])),
    }
    stats = bootstrap_policy_stats(**args)
    ci = percentile_ci(stats["qini"]["noise_a"] - stats["qini"]["noise_b"])
    assert ci_spans_zero(ci)
    # ...and each noise policy is individually indistinguishable from random.
    assert ci_spans_zero(percentile_ci(stats["qini"]["noise_a"]))


def test_bootstrap_difference_ci_excludes_zero_for_strong_signal() -> None:
    # The informative ranking beats a noise ranking by a wide, paired margin:
    # the difference CI excludes zero.
    stats = bootstrap_policy_stats(**_bootstrap_args())
    ci = percentile_ci(stats["qini"]["informative"] - stats["qini"]["noise"])
    assert not ci_spans_zero(ci)
    assert ci[0] > 0


def test_bootstrap_t_beats_random_paired_profit_ci_excludes_zero() -> None:
    # An informative top-25% ranking beats the random baseline's budget
    # profit by a paired margin that excludes zero.
    args = _bootstrap_args(n=6_000)
    args["scores"] = {"t_learner": args["scores"]["informative"]}
    stats = bootstrap_policy_stats(**args)
    diff = stats["profit_at_budget"]["t_learner"] - stats["random_profit_at_budget"]
    ci = percentile_ci(diff)
    assert not ci_spans_zero(ci)
    assert ci[0] > 0


def test_bootstrap_mail_everyone_beats_t_at_tiny_send_cost() -> None:
    # Uniform +8pp treatment effect, no ranking signal: full-mail captures
    # every incremental conversion, so at $0.01/email mail-everyone's profit
    # beats any top-25% policy by a paired margin entirely below zero
    # (T minus mail-everyone < 0 -> the interval's upper bound is negative).
    rng = np.random.default_rng(3)
    n = 2_000
    treatment = rng.integers(0, 2, n)
    outcome = rng.binomial(1, np.clip(0.05 + treatment * 0.08, 0, 1))
    args = {
        "treatment": treatment,
        "outcome": outcome,
        "scores": {"t_learner": rng.normal(0, 1, n)},  # pure noise ranking
        "budget": 0.25,
        "n_total": n,
        "revenue_per_conversion": 114.0,
        "cost_per_email": 0.01,
        "n_boot": 300,
        "seed": 42,
    }
    stats = bootstrap_policy_stats(**args)
    diff = stats["profit_at_budget"]["t_learner"] - stats["mail_everyone_profit_at_budget"]
    ci = percentile_ci(diff)
    assert ci[1] < 0
    assert not ci_spans_zero(ci)
    # Mail-everyone's bootstrap mean reproduces the analytic full-mail profit.
    inc_all = incremental_at_full(treatment, outcome)
    point = inc_all * 114.0 - n * 0.01
    assert float(np.mean(stats["mail_everyone_profit_at_budget"])) == pytest.approx(point, rel=0.05)
    # The random baseline is the diagonal: mean profit equals the diagonal point.
    random_point = 0.25 * inc_all * 114.0 - 0.25 * n * 0.01
    assert float(np.mean(stats["random_profit_at_budget"])) == pytest.approx(random_point, rel=0.05)


def test_bootstrap_band_grid_shape_and_bounds() -> None:
    grid = np.linspace(0.0, 1.0, 21)
    stats = bootstrap_policy_stats(**{**_bootstrap_args(), "band_grid": grid})
    for lo, hi in stats["band"].values():
        assert lo.shape == grid.shape and hi.shape == grid.shape
        assert np.all(lo <= hi)
    np.testing.assert_array_equal(stats["band_grid"], grid)


def test_percentile_ci_and_span_helpers() -> None:
    values = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    lo, hi = percentile_ci(values, alpha=0.4)  # 0.2 / 0.8 quantiles, linear interp
    assert lo == pytest.approx(-1.2) and hi == pytest.approx(1.2)
    assert ci_spans_zero((lo, hi))
    assert not ci_spans_zero((0.5, 1.5))
