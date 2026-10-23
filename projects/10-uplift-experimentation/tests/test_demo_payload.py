"""Demo payload contract: deterministic lookup data for the uplift simulator UI."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from uplift_experimentation.config import UpliftConfig
from uplift_experimentation.demo_payload import (
    DEMO_COSTS,
    DEMO_FRACTIONS,
    build_demo_payload,
    write_demo_payload,
)
from uplift_experimentation.multiarm import (
    arm_shares,
    assigned_uplift,
    estimated_qini_curve,
    per_arm_qini_read,
    recommend_arm,
)

SEGMENTS = ["Mens E-Mail", "Womens E-Mail", "No E-Mail"]
TWO_ARM_BREAK_EVEN = 0.29989329115278707
MULTI_ARM_BREAK_EVEN = 0.30800752330508424


@pytest.fixture
def demo_context(tmp_path: Path) -> tuple[UpliftConfig, pd.DataFrame]:
    """Minimal on-disk context: small scored three-arm frame + committed-metrics shape."""
    rng = np.random.default_rng(11)
    n = 3_000
    seg = np.array(["Mens E-Mail"] * 1_000 + ["Womens E-Mail"] * 1_000 + ["No E-Mail"] * 1_000)
    high = rng.random(n) < 0.3
    u_m = np.where(seg == "Mens E-Mail", 0.02, 0.0) + np.where(high, 0.01, 0.0)
    u_w = np.where(seg == "Womens E-Mail", 0.012, 0.0) + np.where(high, 0.005, 0.0)
    p = 0.006 + (seg == "Mens E-Mail") * 0.02 + (seg == "Womens E-Mail") * 0.012
    conversion = rng.binomial(1, np.clip(p, 0, 1))
    scores = pd.DataFrame(
        {
            "segment": seg,
            "treated_mens": (seg == "Mens E-Mail").astype(int),
            "treated_womens": (seg == "Womens E-Mail").astype(int),
            "conversion": conversion,
            "visit": rng.binomial(1, 0.1, n),
            "spend": conversion * rng.uniform(20, 300, n),
            "uplift_mens": u_m,
            "uplift_womens": u_w,
        }
    )
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    data_dir.mkdir()
    reports_dir.mkdir()
    scores.to_parquet(data_dir / "scores_multi.parquet")

    # Committed-metrics shape: empirical per-arm values are what the same
    # functions produce on this frame; CIs/break-evens ride along as published.
    reads = per_arm_qini_read(seg, conversion.astype(float), u_m, u_w)
    metrics = {
        "_meta": {
            "cost_model": {"revenue_per_conversion": 114.0, "cost_per_email": 0.01},
            "cost_sensitivity": {"breakeven_cost_per_email": TWO_ARM_BREAK_EVEN},
        },
        "multi_arm": {
            "note": "fixture model-estimated note",
            "recommended_arm_shares": arm_shares(recommend_arm(u_m, u_w)),
            "per_arm": {
                arm: {
                    "qini_coefficient": reads[arm]["qini_coefficient"],
                    "incremental_conversions_full": reads[arm]["incremental_conversions_full"],
                    "qini_ci": [-1.0, 2.0],
                    "incremental_conversions_full_ci": [1.0, 5.0],
                }
                for arm in ("mens", "womens")
            },
            "best_arm_break_even": {
                "vs": "mail_everyone_mens",
                "cost_per_email": MULTI_ARM_BREAK_EVEN,
                "policy_budget": 0.25,
                "formula": "fixture formula",
            },
        },
    }
    (reports_dir / "metrics.json").write_text(json.dumps(metrics))
    cfg = UpliftConfig(bootstrap_reps=100, data_dir=data_dir, reports_dir=reports_dir)
    return cfg, scores


@pytest.fixture
def payload(demo_context: tuple[UpliftConfig, pd.DataFrame]) -> dict:
    cfg, _scores = demo_context
    return build_demo_payload(cfg)


def _expected_profit_grids(scores: pd.DataFrame) -> dict[str, np.ndarray]:
    """Client-side recomputation of the profit grids from the raw scores."""
    u_m = scores["uplift_mens"].to_numpy(dtype=float)
    u_w = scores["uplift_womens"].to_numpy(dtype=float)
    est = assigned_uplift(u_m, u_w, recommend_arm(u_m, u_w))
    n = len(scores)
    fractions = np.asarray(DEMO_FRACTIONS)
    costs = np.asarray(DEMO_COSTS)

    def inc_at(estimated: np.ndarray) -> np.ndarray:
        _fr, inc = estimated_qini_curve(estimated)
        idx = np.rint(fractions * len(estimated)).astype(int) - 1
        return inc[1:][idx]

    def grid(inc_at_f: np.ndarray) -> np.ndarray:
        return inc_at_f[None, :] * 114.0 - n * fractions[None, :] * costs[:, None]

    return {
        "best_arm": grid(inc_at(est)),
        "single_arm": grid(inc_at(u_m)),
        "random": grid(fractions * est.sum()),
    }


def test_payload_shape(payload: dict) -> None:
    assert payload["schema_version"] == 1
    assert payload["demo"] == "uplift-simulator"
    assert payload["project"] == "10-uplift-experimentation"
    assert set(payload) == {
        "schema_version",
        "demo",
        "project",
        "n_customers",
        "scalars",
        "profit_grid",
        "qini_points",
        "arm_mix_by_fraction",
        "segments",
    }
    grid = payload["profit_grid"]
    assert grid["costs"] == DEMO_COSTS and len(DEMO_COSTS) == 50
    assert grid["fractions"] == DEMO_FRACTIONS and len(DEMO_FRACTIONS) == 100
    assert grid["n_boot"] == 100 and grid["model_estimated"] is True
    for policy in ("best_arm", "single_arm", "random"):
        profit = grid["policies"][policy]["profit"]
        assert len(profit) == 50 and all(len(row) == 100 for row in profit)
    for policy in ("best_arm", "random"):
        ci = grid["policies"][policy]["ci"]
        assert len(ci["lo"]) == 50 and len(ci["hi"]) == 50
        for lo_row, hi_row in zip(ci["lo"], ci["hi"], strict=True):
            assert all(lo <= hi for lo, hi in zip(lo_row, hi_row, strict=True))
    for arm in ("mens", "womens"):
        pts = payload["qini_points"][arm]
        assert len(pts["fractions"]) == len(pts["incremental"]) <= 100
        assert pts["random_fractions"] == [0.0, 1.0]
    assert set(payload["segments"]) == set(SEGMENTS)
    for entry in payload["segments"].values():
        assert set(entry) >= {"n", "visit_rate", "conversion_rate", "mean_spend"}


def test_payload_profit_matches_multiarm_formula(
    demo_context: tuple[UpliftConfig, pd.DataFrame], payload: dict
) -> None:
    """Grid profits must reproduce multiarm's formula given the stored scalars."""
    _cfg, scores = demo_context
    expected = _expected_profit_grids(scores)
    grid = payload["profit_grid"]
    rev = payload["scalars"]["revenue_per_conversion"]
    n = payload["n_customers"]
    assert rev == 114.0 and n == len(scores)
    cost_idx = {c: i for i, c in enumerate(grid["costs"])}
    frac_idx = {f: j for j, f in enumerate(grid["fractions"])}
    for policy, mat in expected.items():
        stored = grid["policies"][policy]["profit"]
        for c in (0.01, 0.31, 0.50):
            for f in (0.25, 1.00):
                i, j = cost_idx[c], frac_idx[f]
                assert stored[i][j] == pytest.approx(mat[i, j], abs=0.01), (policy, c, f)


def test_payload_break_even_committed(payload: dict) -> None:
    """Both committed break-even reads are carried through, labeled."""
    be = payload["scalars"]["break_even"]
    assert be["two_arm_committed"]["cost_per_email"] == pytest.approx(TWO_ARM_BREAK_EVEN)
    assert be["multi_arm_best_arm"]["cost_per_email"] == pytest.approx(
        MULTI_ARM_BREAK_EVEN,
        abs=0.005,  # the published ≈ $0.31 read, within rounding
    )
    assert be["multi_arm_best_arm"]["vs"] == "mail_everyone_mens"
    assert "model-estimated" in payload["scalars"]["model_estimated_note"].lower()


def test_payload_arm_shares_sum_to_one(
    demo_context: tuple[UpliftConfig, pd.DataFrame], payload: dict
) -> None:
    _cfg, scores = demo_context
    shares = payload["scalars"]["recommended_arm_shares"]
    assert set(shares) == {"mens", "womens", "none"}
    assert sum(shares.values()) == pytest.approx(1.0)
    expected = arm_shares(
        recommend_arm(
            scores["uplift_mens"].to_numpy(dtype=float),
            scores["uplift_womens"].to_numpy(dtype=float),
        )
    )
    assert shares == pytest.approx(expected, rel=1e-5)


def test_payload_mail_everyone_profit_formula(payload: dict) -> None:
    """Mail-everyone profit is the exact full-send formula, no bootstrap."""
    scalars = payload["scalars"]
    n, rev = scalars["n_customers"], scalars["revenue_per_conversion"]
    totals = scalars["incremental_conversions_full_send_model_estimated"]
    for arm in ("mens", "womens"):
        profits = scalars["mail_everyone_profit"][arm]
        assert len(profits) == 50
        for cost_str in ("0.01", "0.31", "0.50"):
            cost = float(cost_str)
            expected = totals[arm] * rev - n * cost
            assert profits[cost_str] == pytest.approx(expected, abs=0.01)


def test_payload_arm_mix_by_fraction(
    demo_context: tuple[UpliftConfig, pd.DataFrame], payload: dict
) -> None:
    """Top-k arm mix rides the same lattice; shares sum to 1 at every point."""
    mix = payload["arm_mix_by_fraction"]
    assert mix["fractions"] == DEMO_FRACTIONS and len(DEMO_FRACTIONS) == 100
    assert set(mix["shares"]) == {"mens", "womens", "none"}
    for series in mix["shares"].values():
        assert len(series) == 100
        assert all(0.0 <= s <= 1.0 for s in series)
        assert all(s == round(s, 6) for s in series)
    for i in range(100):
        total = sum(mix["shares"][label][i] for label in ("mens", "womens", "none"))
        assert total == pytest.approx(1.0, abs=2e-6)
    # the k = 100 endpoint is the full-send mix, and the ranking top is more
    # mens-heavy than the full send on this fixture (mens scores dominate)
    for label in ("mens", "womens", "none"):
        assert mix["shares"][label][-1] == pytest.approx(
            payload["scalars"]["recommended_arm_shares"][label], abs=2e-6
        )
    assert mix["shares"]["mens"][4] > mix["shares"]["mens"][99]
    # "none" recommendations sit at score 0, i.e. strictly below every positive
    # score, so the none-share is non-decreasing along the ranking
    none = mix["shares"]["none"]
    assert all(none[i + 1] >= none[i] - 1e-9 for i in range(99))


def test_payload_arm_mix_matches_ranking(
    demo_context: tuple[UpliftConfig, pd.DataFrame], payload: dict
) -> None:
    """Shares reproduce the cumulated recommendation counts over the ranking."""
    _cfg, scores = demo_context
    u_m = scores["uplift_mens"].to_numpy(dtype=float)
    u_w = scores["uplift_womens"].to_numpy(dtype=float)
    recommended = recommend_arm(u_m, u_w)
    best = np.maximum(np.maximum(u_m, u_w), 0.0)
    rec_sorted = recommended[np.argsort(-best, kind="stable")]
    k = int(np.rint(0.25 * len(best)))
    for label in ("mens", "womens", "none"):
        expected = float(np.mean(rec_sorted[:k] == label))
        assert payload["arm_mix_by_fraction"]["shares"][label][24] == pytest.approx(
            expected, abs=2e-6
        )


def test_payload_arm_mix_deterministic(
    demo_context: tuple[UpliftConfig, pd.DataFrame], payload: dict
) -> None:
    cfg, _scores = demo_context
    again = build_demo_payload(cfg)["arm_mix_by_fraction"]
    assert again == payload["arm_mix_by_fraction"]


def test_payload_per_arm_qini_matches_recomputed(
    demo_context: tuple[UpliftConfig, pd.DataFrame], payload: dict
) -> None:
    _cfg, scores = demo_context
    reads = per_arm_qini_read(
        scores["segment"].to_numpy(),
        scores["conversion"].to_numpy(dtype=float),
        scores["uplift_mens"].to_numpy(dtype=float),
        scores["uplift_womens"].to_numpy(dtype=float),
    )
    for arm in ("mens", "womens"):
        entry = payload["scalars"]["per_arm_qini"][arm]
        assert entry["qini_coefficient"] == pytest.approx(reads[arm]["qini_coefficient"])
        assert entry["qini_ci"] == [-1.0, 2.0]  # committed CI rides through


def test_write_demo_payload_deterministic_roundtrip(
    demo_context: tuple[UpliftConfig, pd.DataFrame],
) -> None:
    cfg, _scores = demo_context
    out = write_demo_payload(cfg)
    assert out.name == "demo_payload.json"
    on_disk = json.loads(out.read_text())
    assert on_disk == build_demo_payload(cfg)
    assert (
        on_disk["profit_grid"]["policies"]["best_arm"]["ci"]
        == build_demo_payload(cfg)["profit_grid"]["policies"]["best_arm"]["ci"]
    )
