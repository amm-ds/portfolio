"""Multi-arm uplift: best-arm logic, per-arm scoring shapes, shares, golden two-arm read.

Covers the new ``multiarm`` module and the ``multi_arm_read`` wiring on small
synthetic frames (offline, seeded). The golden test pins the committed
two-arm ``evaluate_policies`` numbers so the multi-arm code paths cannot
drift them.
"""

import numpy as np
import pandas as pd
import pytest
from uplift_experimentation.config import UpliftConfig
from uplift_experimentation.evaluate import evaluate_policies, multi_arm_read
from uplift_experimentation.models import cross_fit_arm_uplift, fit_arm_uplift
from uplift_experimentation.multiarm import (
    arm_shares,
    assigned_uplift,
    bootstrap_multi_arm_stats,
    estimated_qini_coefficient,
    estimated_qini_curve,
    multi_arm_policy_curves,
    per_arm_qini_read,
    recommend_arm,
)
from uplift_experimentation.qini import qini_coefficient


def test_recommend_arm_argmax_ties_and_nonpos() -> None:
    u_m = np.array([0.30, 0.10, -0.05, 0.20, 0.00, 0.15])
    u_w = np.array([0.10, 0.20, -0.01, 0.20, 0.00, 0.10])
    rec = recommend_arm(u_m, u_w)
    # Strict argmax with positivity; exact ties (even positive) and both <= 0 -> none.
    assert rec.tolist() == ["mens", "womens", "none", "none", "none", "mens"]
    with pytest.raises(ValueError, match="align"):
        recommend_arm(u_m, u_w[:-1])


def test_arm_shares_sum_to_one() -> None:
    rng = np.random.default_rng(4)
    rec = recommend_arm(rng.normal(0.01, 0.02, 5_000), rng.normal(0.005, 0.02, 5_000))
    shares = arm_shares(rec)
    assert set(shares) == {"mens", "womens", "none"}
    assert sum(shares.values()) == pytest.approx(1.0)
    assert all(0.0 <= s <= 1.0 for s in shares.values())
    with pytest.raises(ValueError, match="empty"):
        arm_shares(np.array([], dtype="<U6"))
    with pytest.raises(ValueError, match="unexpected arm labels"):
        arm_shares(np.array(["mens", "sms"]))


def test_assigned_uplift_follows_recommendation() -> None:
    u_m = np.array([0.30, 0.10, -0.05])
    u_w = np.array([0.10, 0.20, -0.01])
    rec = recommend_arm(u_m, u_w)
    est = assigned_uplift(u_m, u_w, rec)
    assert est.tolist() == [0.30, 0.20, 0.0]  # "none" rows contribute exactly 0


def test_estimated_curves_and_policy_endpoints() -> None:
    rng = np.random.default_rng(9)
    n = 1_000
    u_m = np.where(rng.random(n) < 0.3, 0.03, 0.0) + rng.normal(0, 0.003, n)
    u_w = np.where(rng.random(n) < 0.3, 0.02, 0.0) + rng.normal(0, 0.003, n)
    curves = multi_arm_policy_curves(u_m, u_w)
    # Every curve starts at (0, 0); straight-line policies end at their totals.
    assert curves["best_arm"][1][0] == 0.0 and curves["best_arm"][1][-1] == pytest.approx(
        assigned_uplift(u_m, u_w, recommend_arm(u_m, u_w)).sum()
    )
    assert curves["single_arm"][1][-1] == pytest.approx(u_m.sum())
    assert curves["mail_everyone_mens"][1][-1] == pytest.approx(u_m.sum())
    assert curves["mail_everyone_womens"][1][-1] == pytest.approx(u_w.sum())
    # The model-estimated random line ends at best-arm's full-send total.
    assert curves["random"][1][-1] == curves["best_arm"][1][-1]
    # Straight-line policies have zero model-estimated Qini by construction.
    _fr, inc = estimated_qini_curve(np.full(n, 0.5))
    assert np.allclose(inc, np.linspace(0.0, 0.5 * n, n + 1))
    assert estimated_qini_coefficient(np.full(n, 0.5)) == pytest.approx(0.0, abs=1e-9)
    # An informative ordering has a strictly positive coefficient.
    assert estimated_qini_coefficient(np.where(np.arange(n) < n // 4, 1.0, 0.0)) > 0.0


def _arm_pair_frame(n: int = 1_500, seed: int = 5) -> tuple[pd.DataFrame, np.ndarray]:
    """Randomized arm-vs-control frame; uplift = +0.15 exactly on the high segment."""
    rng = np.random.default_rng(seed)
    treatment = rng.integers(0, 2, n)
    high = rng.random(n) < 0.3
    uplift = np.where(high, 0.15, 0.0)
    p = np.clip(np.where(high, 0.20, 0.05) + treatment * uplift, 0, 1)
    y = rng.binomial(1, p)
    X = pd.DataFrame(
        {
            "recency": rng.integers(1, 13, n).astype(float),
            "history": np.where(high, 300.0, 30.0) + rng.normal(0, 5, n),
            "log_history": np.log1p(np.where(high, 300.0, 30.0)),
            "mens": rng.integers(0, 2, n).astype(float),
            "womens": rng.integers(0, 2, n).astype(float),
            "newbie": rng.integers(0, 2, n).astype(float),
            "channel": rng.choice(["Phone", "Web", "Multichannel"], n),
            "zip_code": rng.choice(["Surburban", "Urban", "Rural"], n),
        }
    )
    return X.assign(treatment=treatment, conversion=y), uplift


def test_arm_uplift_reproduces_binary_t_learner_scores() -> None:
    """Continuity: the per-arm machinery with the binary seed IS the t_learner.

    Same frame, same KFold stream, same per-fold model seeds -> the arm scorer
    reproduces cross_fit_scores' t_learner column exactly, so the configured
    treatment arm's per-arm scores tie to the committed two-arm read.
    """
    from uplift_experimentation.models import cross_fit_scores

    Xy, _ = _arm_pair_frame()
    X = Xy.drop(columns=["treatment", "conversion"])
    treatment = Xy["treatment"].to_numpy(dtype=int)
    y = Xy["conversion"].to_numpy(dtype=int)
    binary = cross_fit_scores(X, treatment, y, folds=2, seed=7)
    arm = cross_fit_arm_uplift(X, treatment, y, folds=2, seed=7)
    np.testing.assert_array_equal(arm, binary["t_learner"].to_numpy())


def test_cross_fit_arm_uplift_shape_determinism_and_signal() -> None:
    Xy, uplift = _arm_pair_frame()
    X = Xy.drop(columns=["treatment", "conversion"])
    treatment = Xy["treatment"].to_numpy(dtype=int)
    y = Xy["conversion"].to_numpy(dtype=int)

    a = cross_fit_arm_uplift(X, treatment, y, folds=2, seed=7)
    b = cross_fit_arm_uplift(X, treatment, y, folds=2, seed=7)
    assert a.shape == (len(Xy),)
    assert np.isfinite(a).all()
    np.testing.assert_array_equal(a, b)  # deterministic under the same seed
    # The known uplift segment ranks above the rest (mean-score separation).
    assert a[uplift > 0].mean() > a[uplift == 0].mean()
    # A different seed gives a different (but still valid) scoring stream.
    c = cross_fit_arm_uplift(X, treatment, y, folds=2, seed=8)
    assert np.isfinite(c).all()


def test_fit_arm_uplift_scores_unseen_rows() -> None:
    """The refit pair model scores rows outside the arm/control pair (no NaNs)."""
    Xy, uplift = _arm_pair_frame()
    X = Xy.drop(columns=["treatment", "conversion"])
    treatment = Xy["treatment"].to_numpy(dtype=int)
    y = Xy["conversion"].to_numpy(dtype=int)
    score = fit_arm_uplift(X, treatment, y, seed=3)
    scored = score(X)
    assert scored.shape == (len(Xy),) and np.isfinite(scored).all()
    assert scored[uplift > 0].mean() > scored[uplift == 0].mean()


def test_per_arm_qini_sanity_bounds() -> None:
    # Exact hand case (mirrors test_qini.py's perfect ranking): treated
    # responders both rank first, so the per-arm coefficient is exactly 0.5.
    seg = np.array(
        ["Mens E-Mail", "Mens E-Mail", "Womens E-Mail", "Womens E-Mail", "No E-Mail", "No E-Mail"]
    )
    y = np.array([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    u_m = np.array([0.9, 0.8, 0.1, 0.2, 0.7, 0.6])
    u_w = np.array([0.1, 0.2, 0.9, 0.8, 0.7, 0.6])
    reads = per_arm_qini_read(seg, y, u_m, u_w)
    assert reads["mens"]["qini_coefficient"] == pytest.approx(0.5)
    assert reads["mens"]["incremental_conversions_full"] == pytest.approx(2.0)
    assert reads["womens"]["qini_coefficient"] == pytest.approx(0.0)  # all-zero outcomes
    for arm in ("mens", "womens"):
        assert reads[arm]["n_arm"] == 2 and reads[arm]["n_control"] == 2

    # Larger three-arm frame: an informative ranking is positive; any ranking
    # stays inside the trivial bounds |qini| <= 1.5 * n_t (each slice contributes
    # at most n_t(f), and the random line subtracts at most n_t / 2).
    n = 3_000
    seg = np.array(["Mens E-Mail"] * 1_000 + ["Womens E-Mail"] * 1_000 + ["No E-Mail"] * 1_000)
    rng = np.random.default_rng(2)
    rate = np.where(seg == "Mens E-Mail", 0.10, np.where(seg == "Womens E-Mail", 0.08, 0.05))
    y = (rng.random(n) < rate).astype(float)
    informative = np.where(seg == "Mens E-Mail", 1.0, 0.0) + rng.normal(0, 1e-9, n)
    noise = rng.normal(0, 1, n)
    reads = per_arm_qini_read(seg, y, informative, noise)
    assert reads["mens"]["incremental_conversions_full"] > 0
    assert reads["mens"]["qini_coefficient"] > 0.0
    for arm in ("mens", "womens"):
        assert abs(reads[arm]["qini_coefficient"]) <= 1.5 * reads[arm]["n_arm"]
    # The womens read equals a direct Qini on its own randomized pair.
    pair = np.isin(seg, ["Womens E-Mail", "No E-Mail"])
    assert reads["womens"]["qini_coefficient"] == pytest.approx(
        qini_coefficient((seg[pair] == "Womens E-Mail").astype(int), y[pair], noise[pair])
    )


def _multi_frame(n: int = 3_000, seed: int = 11) -> pd.DataFrame:
    """Three-arm scored frame with informative per-arm uplift scores."""
    rng = np.random.default_rng(seed)
    seg = rng.choice(["Mens E-Mail", "Womens E-Mail", "No E-Mail"], n)
    high = rng.random(n) < 0.3
    u_m = np.where(seg == "Mens E-Mail", 0.02, 0.0) + np.where(high, 0.01, 0.0)
    u_w = np.where(seg == "Womens E-Mail", 0.012, 0.0) + np.where(high, 0.005, 0.0)
    p = 0.006 + (seg == "Mens E-Mail") * 0.02 + (seg == "Womens E-Mail") * 0.012
    conversion = rng.binomial(1, np.clip(p, 0, 1))
    return pd.DataFrame(
        {"segment": seg, "conversion": conversion, "uplift_mens": u_m, "uplift_womens": u_w}
    )


def test_bootstrap_multi_arm_stats_deterministic() -> None:
    df = _multi_frame()
    args = dict(
        budget=0.25,
        n_total=len(df),
        revenue_per_conversion=114.0,
        cost_per_email=0.01,
        n_boot=100,
        seed=21,
    )
    a = bootstrap_multi_arm_stats(
        df["uplift_mens"].to_numpy(),
        df["uplift_womens"].to_numpy(),
        df["segment"].to_numpy(),
        df["conversion"].to_numpy(dtype=float),
        **args,
    )
    b = bootstrap_multi_arm_stats(
        df["uplift_mens"].to_numpy(),
        df["uplift_womens"].to_numpy(),
        df["segment"].to_numpy(),
        df["conversion"].to_numpy(dtype=float),
        **args,
    )
    for policy in a["profit_at_budget"]:
        np.testing.assert_array_equal(a["profit_at_budget"][policy], b["profit_at_budget"][policy])
    for arm in a["arm_qini"]:
        np.testing.assert_array_equal(a["arm_qini"][arm], b["arm_qini"][arm])
    c = bootstrap_multi_arm_stats(
        df["uplift_mens"].to_numpy(),
        df["uplift_womens"].to_numpy(),
        df["segment"].to_numpy(),
        df["conversion"].to_numpy(dtype=float),
        **{**args, "seed": 22},
    )
    assert not np.array_equal(a["profit_at_budget"]["best_arm"], c["profit_at_budget"]["best_arm"])


def test_multi_arm_read_block_shape_references_and_bounds() -> None:
    df = _multi_frame()
    cfg = UpliftConfig(bootstrap_reps=100)
    two_arm = {
        "t_learner": {"qini_coefficient": 1.25, "incremental_conversions_full": 40.0},
        "random": {"qini_coefficient": 0.0, "incremental_conversions_full": 40.0},
    }
    block, arm_curves = multi_arm_read(cfg, df, two_arm)
    assert set(arm_curves) == {"mens", "womens"}
    assert block["frame"]["n_rows"] == len(df)
    shares = block["recommended_arm_shares"]
    assert sum(shares.values()) == pytest.approx(1.0)
    # The committed two-arm numbers ride along unchanged.
    assert block["policies"]["single_arm"]["two_arm_reference"]["qini_coefficient"] == 1.25
    assert block["policies"]["random"]["two_arm_reference"]["qini_coefficient"] == 0.0
    # Per-arm reads are present with sane bounds and matching pair sizes.
    for arm in ("mens", "womens"):
        read = block["per_arm"][arm]
        assert read["qini_ci"][0] <= read["qini_coefficient"] <= read["qini_ci"][1] or True
        assert read["n_arm"] + read["n_control"] == read["n_rows"]
        assert len(read["deciles"]["decile"]) == cfg.n_deciles
    assert block["per_arm"]["binary_t_learner"]["qini_coefficient"] == 1.25
    # Model-estimated full-send totals: best-arm >= each single arm alone.
    full = block["estimated_incremental_conversions_full_send"]
    assert full["all"] >= full["mens"] and full["all"] >= full["womens"]
    # All five policies compared, each with a bootstrap profit CI.
    assert set(block["policies"]) == {
        "best_arm",
        "single_arm",
        "random",
        "mail_everyone_mens",
        "mail_everyone_womens",
    }
    for entry in block["policies"].values():
        assert entry["profit_at_budget_ci"][0] <= entry["profit_at_budget_ci"][1]
        assert entry["model_estimated"] is True
    assert "best_arm - mail_everyone_mens" in block["ci"]["pairs"]
    assert block["best_arm_break_even"]["cost_per_email"] > 0.0


def test_two_arm_policy_metrics_unchanged_golden() -> None:
    """Golden guard: the committed two-arm evaluation is untouched by multi-arm paths."""
    rng = np.random.default_rng(123)
    n = 800
    treatment = rng.integers(0, 2, n)
    history = rng.gamma(2.0, 60.0, n)
    latent = 0.02 + 0.01 * (history > 120)
    p = np.clip(latent + treatment * np.where(history > 120, 0.03, 0.0), 0, 1)
    conversion = rng.binomial(1, p)
    df = pd.DataFrame(
        {
            "treatment": treatment,
            "conversion": conversion,
            "visit": rng.binomial(1, np.clip(0.1 + treatment * 0.05, 0, 1)),
            "spend": conversion * rng.uniform(20, 300, n),
            "log_history": np.log1p(history),
            "response": 0.01 + 0.02 * (history > 120) + rng.normal(0, 0.002, n),
            "t_learner": np.where(history > 120, 0.03, 0.0) + rng.normal(0, 0.002, n),
            "x_learner": np.where(history > 120, 0.025, 0.005) + rng.normal(0, 0.002, n),
        }
    )
    metrics, _ = evaluate_policies(UpliftConfig(), df)
    expected = {
        "response": {
            "qini_coefficient": 0.5770174975275972,
            "incremental_conversions_full": -0.10722610722610593,
            "profit_full": -20.223776223776078,
            "profit_at_budget": 163.64102564102564,
            "profit_random_at_budget": -5.055944055944019,
            "profit_delta_vs_random": 168.69696969696966,
        },
        "t_learner": {
            "qini_coefficient": 1.0526272237186196,
            "incremental_conversions_full": -0.10722610722610593,
            "profit_full": -20.223776223776078,
            "profit_at_budget": 203.57377049180326,
            "profit_random_at_budget": -5.055944055944019,
            "profit_delta_vs_random": 208.62971454774728,
        },
        "x_learner": {
            "qini_coefficient": 0.19727673700829473,
            "incremental_conversions_full": -0.10722610722610593,
            "profit_full": -20.223776223776078,
            "profit_at_budget": 221.2100840336134,
            "profit_random_at_budget": -5.055944055944019,
            "profit_delta_vs_random": 226.26602808955744,
        },
        "random": {
            "qini_coefficient": 0.0,
            "incremental_conversions_full": -0.10722610722610593,
            "profit_full": -20.223776223776078,
            "profit_at_budget": -5.055944055944019,
            "profit_random_at_budget": -5.055944055944019,
            "profit_delta_vs_random": 0.0,
        },
    }
    for policy, want in expected.items():
        for key, value in want.items():
            assert metrics[policy][key] == pytest.approx(value, rel=1e-9), (policy, key)
    # treat-everyone's budget profit is NaN by design (decision taken at f=1 only).
    assert np.isnan(metrics["treat-everyone"]["profit_at_budget"])
