"""Meta-learners on synthetic data with a known uplift structure, plus the
evaluate-stage reads (CUPED/power/policy metrics) on locally scored frames."""

import numpy as np
import pandas as pd
import polars as pl
import pytest
from uplift_experimentation.config import UpliftConfig
from uplift_experimentation.evaluate import cuped_read, evaluate_policies, power_analysis
from uplift_experimentation.models import cross_fit_scores


def _make_uplift_frame(n: int = 4_000, seed: int = 5) -> tuple[pd.DataFrame, np.ndarray]:
    """Randomized arms; uplift = +0.15 exactly on the high-history segment."""
    rng = np.random.default_rng(seed)
    treatment = rng.integers(0, 2, n)
    high = rng.random(n) < 0.3
    base = np.where(high, 0.20, 0.05)
    uplift = np.where(high, 0.15, 0.0)
    p = np.clip(base + treatment * uplift, 0, 1)
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


def _features(df: pd.DataFrame) -> pd.DataFrame:
    """The eight pre-treatment covariates the models expect, from a local frame."""
    n = len(df)
    return pd.DataFrame(
        {
            "recency": np.full(n, 5.0),
            "history": df["log_history"].to_numpy(),
            "log_history": df["log_history"].to_numpy(),
            "mens": np.zeros(n),
            "womens": np.zeros(n),
            "newbie": np.zeros(n),
            "channel": np.full(n, "Web"),
            "zip_code": np.full(n, "Urban"),
        }
    )


def test_t_and_x_learners_rank_known_uplift_segment() -> None:
    Xy, uplift = _make_uplift_frame()
    X = Xy.drop(columns=["treatment", "conversion"])
    treatment = Xy["treatment"].to_numpy(dtype=int)
    y = Xy["conversion"].to_numpy(dtype=int)

    scores = cross_fit_scores(X, treatment, y, folds=2, seed=7)

    for policy in ("t_learner", "x_learner"):
        mean_score_high = scores.loc[uplift > 0, policy].mean()
        mean_score_low = scores.loc[uplift == 0, policy].mean()
        assert mean_score_high > mean_score_low, f"{policy} misses the uplift segment"


def test_scores_columns_and_no_nulls(two_arm_frame: pd.DataFrame) -> None:
    scores = cross_fit_scores(
        _features(two_arm_frame),
        two_arm_frame["treatment"].to_numpy(dtype=int),
        two_arm_frame["conversion"].to_numpy(dtype=int),
        folds=2,
        seed=3,
    )
    assert list(scores.columns) == ["response", "t_learner", "x_learner"]
    assert not scores.isnull().any().any()
    assert len(scores) == len(two_arm_frame)
    # Parquet round-trip keeps the schema the evaluate stage expects.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = f"{tmp}/scores.parquet"
        scores.to_parquet(path)
        back = pd.read_parquet(path)
        assert list(back.columns) == list(scores.columns)


def test_evaluate_policies_metrics_shape(two_arm_frame: pd.DataFrame) -> None:
    scores = cross_fit_scores(
        _features(two_arm_frame),
        two_arm_frame["treatment"].to_numpy(dtype=int),
        two_arm_frame["conversion"].to_numpy(dtype=int),
        folds=2,
        seed=3,
    )
    df = pd.concat([two_arm_frame.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)
    cfg = UpliftConfig()
    metrics, curves = evaluate_policies(cfg, df)
    for policy in ("response", "t_learner", "x_learner", "random", "treat-everyone"):
        assert policy in metrics
        assert "qini_coefficient" in metrics[policy]
        assert "profit_at_budget" in metrics[policy]
    assert "random" in curves and "x_learner" in curves
    # Random and treat-everyone sit on the random line: zero Qini by construction.
    assert metrics["random"]["qini_coefficient"] == 0.0
    assert metrics["treat-everyone"]["qini_coefficient"] == 0.0
    # The full-mail profit is identical for random and treat-everyone.
    assert metrics["random"]["profit_full"] == metrics["treat-everyone"]["profit_full"]
    # Model policies carry a real (non-degenerate) profit read at the budget.
    for policy in ("response", "t_learner", "x_learner"):
        assert np.isfinite(metrics[policy]["profit_at_budget"])


def test_cuped_and_power_reads_on_local_frame(two_arm_frame: pd.DataFrame) -> None:
    cfg = UpliftConfig()
    cuped = cuped_read(cfg, two_arm_frame)
    for outcome in ("conversion", "visit"):
        read = cuped[outcome]
        assert 0.0 < read["variance_reduction"] < 1.0
        assert np.isfinite(read["ate_cuped"])
        assert read["ate_se_cuped"] <= read["ate_se_naive"]
    power = power_analysis(cfg, two_arm_frame)
    assert power["n_per_arm"] >= 1
    n_t = int(two_arm_frame["treatment"].sum())
    assert power["actual_per_arm"] == min(n_t, len(two_arm_frame) - n_t)


def test_polars_fixture_two_arm(two_arm_frame: pd.DataFrame) -> None:
    pl.from_pandas(two_arm_frame)  # the prepared frame round-trips to polars


def test_bootstrap_ci_and_cost_sensitivity_reads(two_arm_frame: pd.DataFrame) -> None:
    """The evaluate-stage CI + cost-sensitivity wiring on a local frame."""
    from uplift_experimentation.evaluate import (
        bootstrap_ci_read,
        cost_sensitivity_figure,
        cost_sensitivity_read,
        qini_figure,
    )

    df = two_arm_frame.copy()
    # Uplift in this fixture lives on history > 120, so log_history is an
    # informative ranking direction for every policy.
    df["response"] = df["log_history"]
    df["t_learner"] = df["log_history"] + 1e-6
    df["x_learner"] = df["log_history"] * 0.5
    cfg = UpliftConfig(bootstrap_reps=200)

    ci, bands, grid = bootstrap_ci_read(cfg, df)
    assert set(ci["policies"]) == {"response", "t_learner", "x_learner"}
    for read in ci["policies"].values():
        assert read["qini_ci"][0] <= read["qini_ci"][1]
        assert read["profit_at_budget_ci"][0] <= read["profit_at_budget_ci"][1]
    assert "response - t_learner" in ci["pairs"]
    pair = ci["pairs"]["response - t_learner"]
    assert pair["qini_diff_spans_zero"] == (
        pair["qini_diff_ci"][0] <= 0.0 <= pair["qini_diff_ci"][1]
    )
    # Bands are quantile ribbons on the shared grid, ordered lo <= hi.
    for lo, hi in bands.values():
        assert lo.shape == grid.shape and np.all(lo <= hi)

    # Cost sensitivity on a deterministic curve: 30 incremental conversions
    # total, 25 of them inside the top 30% — a stable concentration read.
    fr = np.linspace(0.0, 1.0, 101)
    inc = 30.0 * np.minimum(fr / 0.3, 1.0)
    curves = {"t_learner": (fr, inc)}
    cs = cost_sensitivity_read(cfg, curves, "t_learner", n_total=10_000)
    assert len(cs["rows"]) == len(cfg.cost_grid)
    # breakeven = revenue * (inc(1) - inc(0.25)) / (N * (1 - 0.25))
    assert cs["breakeven_cost_per_email"] == pytest.approx(114.0 * 5.0 / 7_500.0, rel=1e-3)
    mail = [r["profit_mail_everyone"] for r in cs["rows"]]
    assert mail == sorted(mail, reverse=True)  # mail profit falls with send cost
    assert cs["rows"][-1]["targeting_beats_mail_everyone"]
    qini_figure(curves, "t_learner", bands, grid)  # banded figure builds cleanly
    cost_sensitivity_figure(cs, cfg)
