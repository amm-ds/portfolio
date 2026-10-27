"""Wave-23b hierarchy-explorer payload: hand-checked behaviour on the tiny
3-bottom toy hierarchy (the test_hierarchical.py convention: node order
``['total', 'a', 'b', 'c']``, bottom series a/b/c, S the exact aggregation).

The committed-metrics fixture runs the REAL scoring core (``score_hierarchy``)
on the toy hierarchy and writes the committed-block shape, so the builder's
drift guards, catalog selection, and per-node curves are exercised against a
genuine committed block — exactly the regeneration path the CLI uses against
``reports_hier/metrics.json``. All tests are offline (the autouse network
guard stays on) and fast (<2 min total: the toy is 4 nodes x 3 origins).
"""

import json

import numpy as np
import pandas as pd
import pytest
from demand_forecasting.config import ForecastConfig
from demand_forecasting.hier_demo_payload import (
    CURVE_VARIANTS,
    N_ORIGINS_PER_GROUP,
    PAYLOAD_SCHEMA_VERSION,
    _select_catalog,
    build_hier_demo_payload,
)
from demand_forecasting.hierarchical import (
    GroupSpec,
    _score_origin,
    build_S_df,
    origin_indices,
    score_hierarchy,
)

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
TOY_SPEC = GroupSpec(freq="QE", season_length=4, horizon=2, min_train=20, n_origins=3)
TOY_QUOTAS = {"bottom": 2}


def _toy_frames() -> tuple[pd.DataFrame, np.ndarray, dict[str, np.ndarray], GroupSpec]:
    """28 quarters of an exactly-aggregating tiny hierarchy (3 bottom + total)."""
    rng = np.random.default_rng(0)
    t = np.arange(28)
    a = 100 + np.cumsum(rng.normal(0, 5, 28)) + 10 * np.sin(t * np.pi / 2)
    b = 80 + np.cumsum(rng.normal(0, 4, 28)) + 8 * np.cos(t * np.pi / 2)
    c = 60 + np.cumsum(rng.normal(0, 3, 28)) + 0.5 * t
    frames = []
    ds = pd.date_range("2000-03-31", periods=28, freq="QE")
    for uid, y in (("total", a + b + c), ("a", a), ("b", b), ("c", c)):
        frames.append(pd.DataFrame({"unique_id": uid, "ds": ds, "y": y}))
    return pd.concat(frames, ignore_index=True), TINY_S, TINY_TAGS, TOY_SPEC


@pytest.fixture(scope="module")
def toy_context() -> dict[str, object]:
    """Committed-metrics fixture: score the toy hierarchy once and shape the
    payload build exactly like the CLI path (metrics dict + group frames)."""
    Y_df, S, tags, spec = _toy_frames()
    block, pooled = score_hierarchy("Toy", Y_df, S, tags, spec, ForecastConfig())
    metrics = {"groups": {"Toy": block}}
    payload = build_hier_demo_payload(
        metrics,
        {"Toy": (Y_df, S, tags, spec)},
        ForecastConfig(),
        catalog_quotas={"Toy": TOY_QUOTAS},
    )
    return {
        "Y_df": Y_df,
        "S": S,
        "tags": tags,
        "spec": spec,
        "block": block,
        "pooled": pooled,
        "metrics": metrics,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Hierarchy structure helpers on a 3-level hand hierarchy
# ---------------------------------------------------------------------------

THREE_UIDS = ["total", "ab", "c", "a", "b", "cc"]
THREE_S = np.array(
    [
        [1.0, 1.0, 1.0],  # total = a + b + cc
        [1.0, 1.0, 0.0],  # ab    = a + b
        [0.0, 0.0, 1.0],  # c     = cc
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
)


THREE_TAGS = {
    "total": np.array(["total"]),
    "mid": np.array(["ab", "c"]),
    "bottom": np.array(["a", "b", "cc"]),
}


def test_children_and_parent_path_on_three_level_hierarchy() -> None:
    """Immediate children on a 3-level tree: the total's children are the two
    mid-level nodes only (NOT the bottom series — the wave-23b bug class:
    overcounting every descendant as a child tripled the child sum), and a
    single-child chain (c's set equals cc's) still parents correctly."""
    from demand_forecasting.hier_demo_payload import _HierarchyNav
    from demand_forecasting.hierarchical import level_members, level_names

    nav = _HierarchyNav(THREE_S, THREE_UIDS, level_names(THREE_TAGS), level_members(THREE_TAGS))
    children = {u: nav.children(u) for u in THREE_UIDS}
    assert children["total"] == ["ab", "c"]
    assert children["ab"] == ["a", "b"]
    assert children["c"] == ["cc"]
    assert children["a"] == children["b"] == children["cc"] == []
    assert nav.parent_path("total") == []
    assert nav.parent_path("ab") == ["total"]
    assert nav.parent_path("cc") == ["total", "c"]


# ---------------------------------------------------------------------------
# Payload shape
# ---------------------------------------------------------------------------


def test_payload_shape(toy_context: dict[str, object]) -> None:
    payload = toy_context["payload"]
    assert payload["schema_version"] == PAYLOAD_SCHEMA_VERSION
    assert payload["demo"] == "hierarchy-explorer"
    assert payload["project"] == "02-demand-forecasting"
    for key in ("groups", "catalog", "evaluation_metadata"):
        assert key in payload
    # per-group block carries the committed per-level rmae/coherence/headline
    group_block = payload["groups"]["Toy"]
    for key in ("levels", "origins", "candidates", "per_level", "coherence", "headline"):
        assert key in group_block
    assert group_block["per_level"]["seasonal_naive"]["total"]["rmae"] == pytest.approx(1.0)
    catalog = payload["catalog"]
    assert len(catalog) == 1 + TOY_QUOTAS["bottom"]  # total + top-2 bottom
    block = toy_context["block"]
    committed_origins = block["origins"]["dates"][-N_ORIGINS_PER_GROUP:]
    assert len(committed_origins) == 3
    for entry in catalog:
        assert entry["group"] == "Toy"
        for key in ("node", "level", "parent_path", "children_count", "origins"):
            assert key in entry
        assert len(entry["origins"]) == len(committed_origins)
        for origin_entry in entry["origins"]:
            assert origin_entry["origin"] in committed_origins
            # history = 2 seasonal cycles, actuals + curves = the horizon
            assert len(origin_entry["history"]["y"]) == 2 * TOY_SPEC.season_length
            assert len(origin_entry["actuals"]["y"]) == TOY_SPEC.horizon
            assert set(origin_entry["models"]) == set(CURVE_VARIANTS)
            for model in origin_entry["models"].values():
                assert len(model["y_pred"]) == TOY_SPEC.horizon
    # hierarchy structure: total has 3 children and an empty parent path;
    # bottom nodes have the total as their only ancestor
    by_node = {e["node"]: e for e in catalog}
    assert by_node["total"]["parent_path"] == []
    assert by_node["total"]["children_count"] == 3
    for node in ("a", "b"):
        assert by_node[node]["parent_path"] == ["total"]
        assert by_node[node]["children_count"] == 0
        assert "coherence" not in by_node[node]["origins"][0]  # no children
    # parent nodes carry the reconciled variants' coherence (0.0 on the toy:
    # the reconciliation is exactly coherent)
    total_origin = by_node["total"]["origins"][0]
    assert set(total_origin["coherence"]) == {"lgbm_global+bottom_up", "lgbm_global+mint_shrink"}
    assert total_origin["coherence"]["lgbm_global+bottom_up"] == pytest.approx(0.0, abs=1e-6)


def test_origins_are_the_three_most_recent_committed(toy_context: dict[str, object]) -> None:
    payload = toy_context["payload"]
    block = toy_context["block"]
    expected = block["origins"]["dates"][-N_ORIGINS_PER_GROUP:]
    for entry in payload["catalog"]:
        assert [o["origin"] for o in entry["origins"]] == expected
    meta = payload["evaluation_metadata"]
    assert meta["origins"]["Toy"]["catalog_origins"] == expected
    assert meta["protocol"] == block["protocol"]
    assert meta["source"] == "reports_hier/metrics.json"


# ---------------------------------------------------------------------------
# Catalog selection determinism
# ---------------------------------------------------------------------------


def test_catalog_selection_is_deterministic_volume_based(toy_context: dict[str, object]) -> None:
    Y_df = toy_context["Y_df"]
    tags = toy_context["tags"]
    first = _select_catalog(Y_df, tags, TOY_QUOTAS)
    second = _select_catalog(Y_df, tags, TOY_QUOTAS)
    assert first == second
    # total first, then the top-2 bottom nodes by volume (tie-break: node id)
    vol = Y_df.groupby("unique_id")["y"].sum()
    expected_bottom = sorted(TINY_BOTTOM, key=lambda u: (-vol[u], u))[: TOY_QUOTAS["bottom"]]
    assert first == ["total", *expected_bottom]
    # a quota of zero picks only the total
    assert _select_catalog(Y_df, tags, {}) == ["total"]


# ---------------------------------------------------------------------------
# Curves match a direct call of the underlying scoring functions
# ---------------------------------------------------------------------------


def test_payload_curves_match_direct_score_origin(toy_context: dict[str, object]) -> None:
    """The payload curves ARE the scoring core's outputs (no re-derivation):
    compare against a direct ``_score_origin`` call at the last committed
    origin, the same cross-check the wave-23a smoke test uses."""
    Y_df = toy_context["Y_df"]
    S = toy_context["S"]
    spec = toy_context["spec"]
    block = toy_context["block"]
    payload = toy_context["payload"]
    dates = np.sort(Y_df["ds"].unique())
    origin = origin_indices(len(dates), spec)[-1]
    cutoff = dates[origin]
    train = Y_df[Y_df["ds"] <= cutoff].reset_index(drop=True)
    window = Y_df[(Y_df["ds"] > cutoff) & (Y_df["ds"] <= dates[origin + spec.horizon])].reset_index(
        drop=True
    )
    scored, _ = _score_origin(
        train,
        window,
        TINY_UIDS,
        build_S_df(S, TINY_UIDS, TINY_BOTTOM),
        TINY_TAGS,
        S,
        spec,
        ForecastConfig(),
    )
    origin_date = block["origins"]["dates"][-1]
    by_node = {e["node"]: e for e in payload["catalog"]}
    for node in ("total", "a"):
        sub = scored[scored["unique_id"] == node].sort_values("ds")
        origin_block = next(o for o in by_node[node]["origins"] if o["origin"] == origin_date)
        for variant in CURVE_VARIANTS:
            direct = [round(float(v), 4) for v in sub[variant].to_numpy()]
            assert origin_block["models"][variant]["y_pred"] == direct
        actual = [round(float(v), 4) for v in sub["actual"].to_numpy()]
        assert origin_block["actuals"]["y"] == actual
        # history ends at the origin (the last train period), 2 cycles back
        hist = origin_block["history"]
        assert hist["dates"][-1] == str(pd.Timestamp(cutoff).date())
        assert len(hist["y"]) == 2 * spec.season_length


# ---------------------------------------------------------------------------
# Drift guard: tampered committed metrics raise
# ---------------------------------------------------------------------------


def test_drift_guard_raises_on_tampered_metrics(toy_context: dict[str, object]) -> None:
    Y_df = toy_context["Y_df"]
    S = toy_context["S"]
    tags = toy_context["tags"]
    spec = toy_context["spec"]
    block = toy_context["block"]
    tampered = json.loads(json.dumps({"groups": {"Toy": block}}))
    tampered["groups"]["Toy"]["per_level"]["seasonal_naive"]["total"]["mae"] *= 1.01
    with pytest.raises(ValueError, match="drift guard"):
        build_hier_demo_payload(
            tampered,
            {"Toy": (Y_df, S, tags, spec)},
            ForecastConfig(),
            catalog_quotas={"Toy": TOY_QUOTAS},
        )
    # coherence tamper is caught too (the copied block carries it)
    tampered2 = json.loads(json.dumps({"groups": {"Toy": block}}))
    tampered2["groups"]["Toy"]["coherence"]["auto_ets"] += 1.0
    with pytest.raises(ValueError, match="drift guard"):
        build_hier_demo_payload(
            tampered2,
            {"Toy": (Y_df, S, tags, spec)},
            ForecastConfig(),
            catalog_quotas={"Toy": TOY_QUOTAS},
        )


# ---------------------------------------------------------------------------
# Determinism: run-twice byte identity
# ---------------------------------------------------------------------------


def test_run_twice_byte_identity(toy_context: dict[str, object]) -> None:
    """Two full builds (two full re-scores of the toy hierarchy) produce the
    byte-identical payload — the same determinism contract the committed
    reports_hier/metrics.json carries."""
    Y_df = toy_context["Y_df"]
    S = toy_context["S"]
    tags = toy_context["tags"]
    spec = toy_context["spec"]
    metrics = toy_context["metrics"]
    frames = {"Toy": (Y_df, S, tags, spec)}
    first = build_hier_demo_payload(
        metrics, frames, ForecastConfig(), catalog_quotas={"Toy": TOY_QUOTAS}
    )
    second = build_hier_demo_payload(
        metrics, frames, ForecastConfig(), catalog_quotas={"Toy": TOY_QUOTAS}
    )
    assert json.dumps(first, indent=2) == json.dumps(second, indent=2)


# ---------------------------------------------------------------------------
# Direct scoring-core import sanity (no duplicated model code)
# ---------------------------------------------------------------------------


def test_builder_uses_the_scoring_core() -> None:
    """The payload module must not re-implement scoring: it delegates to the
    hierarchical track's ``score_hierarchy``/``mae_rmae_by_level``, which the
    wave-23a tests pin."""
    import demand_forecasting.hierarchical as hierarchical
    from demand_forecasting import hier_demo_payload

    assert hier_demo_payload.score_hierarchy is hierarchical.score_hierarchy
    assert hier_demo_payload.mae_rmae_by_level is hierarchical.mae_rmae_by_level
