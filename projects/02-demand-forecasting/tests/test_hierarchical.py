"""Wave-23a hierarchical track: hand-computed math on a tiny hierarchy
(3 bottom series + 1 total), MinT determinism, and a real-data smoke test.

Tiny hierarchy convention: node order ``['total', 'a', 'b', 'c']`` (the total
first, matching the Nixtla ``S`` / ``unique_id`` order contract), bottom
series a/b/c, and::

    S = [[1, 1, 1],     # total = a + b + c
         [1, 0, 0],
         [0, 1, 0],
         [0, 0, 1]]

Real-data tests are offline: the datasets are committed under ``data_hier/``
(see ``data_hier/PROVENANCE.md``) and the autouse network guard stays on.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from datasetsforecast.hierarchical import HierarchicalData
from demand_forecasting.config import ForecastConfig
from demand_forecasting.hierarchical import (
    BOOTSTRAP_REPS,
    CANDIDATES,
    NAIVE,
    PROTOCOL,
    VARIANTS,
    GroupSpec,
    _score_origin,
    build_S_df,
    coherence_error,
    evaluate_group,
    level_members,
    level_names,
    mae_rmae_by_level,
    origin_indices,
    seasonal_naive_fitted,
    seasonal_naive_forecast,
)
from hierarchicalforecast.core import HierarchicalReconciliation
from hierarchicalforecast.methods import BottomUp, MinTrace

PROJECT = Path(__file__).resolve().parents[1]
DATA_HIER = PROJECT / "data_hier"

TINY_UIDS = ["total", "a", "b", "c"]
TINY_BOTTOM = ["a", "b", "c"]
TINY_S = np.array(
    [
        [1.0, 1.0, 1.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
)
TINY_TAGS = {"total": np.array(["total"]), "bottom": np.array(["a", "b", "c"])}
PARENT_ROWS = np.array([0])


# ---------------------------------------------------------------------------
# seasonal_naive: alignment, wraparound, insample fits
# ---------------------------------------------------------------------------


def test_seasonal_naive_alignment_and_wraparound() -> None:
    hist = np.array([1.0, 2.0, 3.0, 4.0])
    np.testing.assert_array_equal(seasonal_naive_forecast(hist, 6, 4), [1, 2, 3, 4, 1, 2])
    # h=1 repeats the most recent same-season actual
    np.testing.assert_array_equal(seasonal_naive_forecast(hist, 1, 4), [1.0])
    # m=2 alternation with a partial cycle reference
    odd = np.array([10.0, 20.0, 30.0])
    np.testing.assert_array_equal(seasonal_naive_forecast(odd, 5, 2), [20, 30, 20, 30, 20])
    with pytest.raises(ValueError):
        seasonal_naive_forecast(np.array([1.0, 2.0]), 3, 4)


def test_seasonal_naive_fitted() -> None:
    hist = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    fitted = seasonal_naive_fitted(hist, 2)
    np.testing.assert_array_equal(fitted[:2], [np.nan, np.nan])
    np.testing.assert_array_equal(fitted[2:], [1, 2, 3, 4])


# ---------------------------------------------------------------------------
# S_df construction, levels, origins
# ---------------------------------------------------------------------------


def test_build_S_df() -> None:
    s_df = build_S_df(TINY_S, TINY_UIDS, TINY_BOTTOM)
    assert list(s_df.columns) == ["unique_id", "a", "b", "c"]
    assert s_df["unique_id"].tolist() == TINY_UIDS
    np.testing.assert_array_equal(s_df[["a", "b", "c"]].to_numpy(), TINY_S)


def test_level_names_and_members() -> None:
    tags = {
        "Country": np.array(["total"]),
        "Country/Purpose": np.array(["hol", "bus"]),
        "Country/Purpose/State": np.array(["hol-x", "hol-y", "bus-x", "bus-y"]),
    }
    assert level_names(tags) == ["total", "Country/Purpose", "bottom"]
    members = level_members(tags)
    assert members["total"] == {"total"}
    assert members["bottom"] == {"hol-x", "hol-y", "bus-x", "bus-y"}


def test_origin_indices_cadence_and_cap() -> None:
    spec = GroupSpec(freq="QE", season_length=4, horizon=4, min_train=24, n_origins=6)
    # 36 periods: eligible 23..31 (9 origins), capped to the 6 newest
    assert origin_indices(36, spec) == [26, 27, 28, 29, 30, 31]
    # short panel -> ValueError
    with pytest.raises(ValueError):
        origin_indices(27, spec)


# ---------------------------------------------------------------------------
# coherence error (hand case)
# ---------------------------------------------------------------------------


def test_coherence_error_hand_case() -> None:
    # one parent ('total', row 0); two window periods
    pred = np.array(
        [
            [10.0, 24.0],  # total fc: 10 then 24
            [3.0, 6.0],  # a
            [4.0, 8.0],  # b
            [1.0, 10.0],  # c  -> children sums 8 and 24
        ]
    )
    actual = np.array(
        [
            [12.0, 24.0],
            [4.0, 6.0],
            [4.0, 8.0],
            [4.0, 10.0],
        ]
    )
    # cells: |10-8|/max(12,1)=2/12 and |24-24|/24=0 -> mean 1/12
    assert coherence_error(pred, actual, TINY_S, PARENT_ROWS) == pytest.approx(1.0 / 12.0)
    # an exactly-coherent forecast scores 0.0
    coherent = pred.copy()
    coherent[0] = pred[1:].sum(axis=0)
    assert coherence_error(coherent, actual, TINY_S, PARENT_ROWS) == 0.0


# ---------------------------------------------------------------------------
# per-level MAE / rmae aggregation (hand case)
# ---------------------------------------------------------------------------


def test_mae_rmae_by_level_hand_case() -> None:
    # two bottom series + total; one origin, two periods
    rows = []
    actuals = {"total": [12.0, 24.0], "a": [4.0, 6.0], "b": [8.0, 18.0]}
    preds_naive = {"total": [10.0, 20.0], "a": [5.0, 5.0], "b": [9.0, 9.0]}
    preds_cand = {"total": [12.0, 24.0], "a": [4.0, 7.0], "b": [7.0, 18.0]}
    for uid in ("total", "a", "b"):
        for j in range(2):
            rows.append(
                {
                    "unique_id": uid,
                    "actual": actuals[uid][j],
                    "seasonal_naive": preds_naive[uid][j],
                    "cand": preds_cand[uid][j],
                }
            )
    pooled = pd.DataFrame(rows)
    members = {"total": {"total"}, "bottom": {"a", "b"}}
    variants = (NAIVE, "cand")
    per_level, naive_mae = mae_rmae_by_level(pooled, members, ["total", "bottom"], variants)
    # naive errors: total |2|+|4|=6 -> 3.0; bottom (1+1+1+9)/4=3.0
    assert naive_mae["total"] == pytest.approx(3.0)
    assert naive_mae["bottom"] == pytest.approx(3.0)
    assert per_level[NAIVE]["total"]["rmae"] == pytest.approx(1.0)
    assert per_level[NAIVE]["bottom"]["rmae"] == pytest.approx(1.0)
    # cand errors: total 0.0; bottom (0+1+1+0)/4=0.5 -> rmae 1/6
    assert per_level["cand"]["total"]["mae"] == pytest.approx(0.0)
    assert per_level["cand"]["bottom"]["mae"] == pytest.approx(0.5)
    assert per_level["cand"]["bottom"]["rmae"] == pytest.approx(0.5 / 3.0)


# ---------------------------------------------------------------------------
# MinT reconciliation on the tiny hierarchy: determinism + coherence
# ---------------------------------------------------------------------------


def _tiny_train() -> pd.DataFrame:
    """8 quarters of an exactly-aggregating tiny hierarchy."""
    rng = np.random.default_rng(0)
    a = 100 + np.cumsum(rng.normal(0, 5, 8)) + 10 * np.sin(np.arange(8) * np.pi / 2)
    b = 80 + np.cumsum(rng.normal(0, 4, 8)) + 8 * np.cos(np.arange(8) * np.pi / 2)
    c = 60 + np.cumsum(rng.normal(0, 3, 8))
    frames = []
    ds = pd.date_range("2000-03-31", periods=8, freq="QE")
    for uid, y in (("total", a + b + c), ("a", a), ("b", b), ("c", c)):
        frames.append(pd.DataFrame({"unique_id": uid, "ds": ds, "y": y}))
    return pd.concat(frames, ignore_index=True)


def _tiny_reconcile() -> pd.DataFrame:
    train = _tiny_train()
    hist = train.pivot(index="ds", columns="unique_id", values="y")[TINY_UIDS].to_numpy()
    fc = seasonal_naive_forecast(hist, 2, 4)  # (2 x 4)
    base = (
        pd.DataFrame(
            fc,
            columns=pd.Index(TINY_UIDS, name="unique_id"),
            index=pd.date_range("2000-09-30", periods=2, freq="QE"),
        )
        .rename_axis("ds")
        .stack()
        .rename("seasonal_naive")
        .reset_index()
    )
    fitted = (
        pd.DataFrame(
            np.column_stack([seasonal_naive_fitted(hist[:, i], 4) for i in range(4)]),
            index=train["ds"].unique(),
            columns=pd.Index(TINY_UIDS, name="unique_id"),
        )
        .rename_axis("ds")
        .stack()
        .rename("seasonal_naive")
        .reset_index()
    )
    y_rec = train.merge(fitted, on=["unique_id", "ds"], how="left")
    rec = HierarchicalReconciliation(reconcilers=[BottomUp(), MinTrace(method="mint_shrink")])
    return rec.reconcile(
        Y_hat_df=base, S_df=build_S_df(TINY_S, TINY_UIDS, TINY_BOTTOM), tags=TINY_TAGS, Y_df=y_rec
    )


def test_mint_reconciliation_is_deterministic_and_coherent() -> None:
    first = _tiny_reconcile()
    second = _tiny_reconcile()
    pd.testing.assert_frame_equal(first, second)  # byte-level determinism
    # reconciled variants are exactly coherent: total == a + b + c per period
    wide = first.set_index(["unique_id", "ds"]).unstack("unique_id")
    for col in ("seasonal_naive/BottomUp", "seasonal_naive/MinTrace_method-mint_shrink"):
        bottom_sum = wide[col][TINY_BOTTOM].sum(axis=1)
        np.testing.assert_allclose(wide[col]["total"], bottom_sum, rtol=0, atol=1e-8)


# ---------------------------------------------------------------------------
# Real-data smoke test (offline; committed datasets)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (DATA_HIER / "hierarchical" / "TourismSmall").exists(), reason="data_hier missing"
)
def test_tourism_small_smoke_structural_invariants() -> None:
    block = evaluate_group(DATA_HIER, "TourismSmall", ForecastConfig(), n_origins=2)
    assert block["protocol"] == PROTOCOL
    assert block["group"] == "TourismSmall"
    assert block["origins"]["n"] == 2
    assert block["levels"][0] == "total" and block["levels"][-1] == "bottom"
    assert block["candidates"] == list(CANDIDATES)
    # every variant scored at every level; floor rmae == 1.0 by construction
    for variant in VARIANTS:
        for level in block["levels"]:
            entry = block["per_level"][variant][level]
            assert entry["mae"] >= 0.0 and entry["rmae"] > 0.0
    for level in block["levels"]:
        assert block["per_level"][NAIVE][level]["rmae"] == pytest.approx(1.0)
    # reconciled variants are coherent (machine tolerance)
    for variant in VARIANTS:
        if variant.endswith(("+bottom_up", "+mint_shrink")):
            assert block["coherence"][variant] < 1e-8
    # raw linear naive is exactly coherent on exactly-aggregating actuals
    assert block["coherence"][NAIVE] == 0.0
    # headline carries the bootstrap contract
    assert block["bootstrap"]["n_boot"] == BOOTSTRAP_REPS
    assert len(block["headline"]["total"]["bootstrap"]["ci95"]) == 2
    assert len(block["headline"]["bottom"]["bootstrap"]["ci95"]) == 2
    # block JSON-serializes (full precision floats) — the committed artefact shape
    json.dumps(block)


def test_smoke_reconciled_totals_match_bottom_sums() -> None:
    """On the real TourismSmall hierarchy, reconciled total == Σ bottom cells."""

    Y_df, S, tags = HierarchicalData.load(str(DATA_HIER), "TourismSmall")
    Y_df = Y_df.copy()
    Y_df["ds"] = pd.to_datetime(Y_df["ds"])
    S = np.asarray(S, dtype=float)
    uids = list(Y_df["unique_id"].unique())
    bottom_ids = [str(u) for u in tags[list(tags.keys())[-1]]]
    spec = GroupSpec(freq="QE", season_length=4, horizon=4, min_train=24, n_origins=2)
    dates = np.sort(Y_df["ds"].unique())
    origin = origin_indices(len(dates), spec)[-1]
    cutoff = dates[origin]
    train = Y_df[Y_df["ds"] <= cutoff].reset_index(drop=True)
    window = Y_df[(Y_df["ds"] > cutoff) & (Y_df["ds"] <= dates[origin + spec.horizon])].reset_index(
        drop=True
    )
    scored, _ = _score_origin(
        train, window, uids, build_S_df(S, uids, bottom_ids), tags, S, spec, ForecastConfig()
    )
    for variant in ("lgbm_global+bottom_up", "lgbm_global+mint_shrink"):
        wide = scored.pivot(index="ds", columns="unique_id", values=variant)
        np.testing.assert_allclose(
            wide["total"].to_numpy(),
            wide[bottom_ids].sum(axis=1).to_numpy(),
            rtol=0,
            atol=1e-4,
        )
    # actuals aggregate exactly (the coherence denominator's premise)
    wide_actual = scored.pivot(index="ds", columns="unique_id", values="actual")
    np.testing.assert_allclose(
        wide_actual["total"].to_numpy(), wide_actual[bottom_ids].sum(axis=1).to_numpy()
    )
