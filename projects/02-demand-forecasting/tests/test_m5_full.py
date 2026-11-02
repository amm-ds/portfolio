"""M5 full-panel track tests: hand-computed toy hierarchy + tiny byte-identity runs.

The hierarchy toys are 3 items x 2 stores with known prices and deliberately
simple demand patterns — the tests recompute one aggregation level (store),
the revenue weights, the first-difference denominators and the final official
WRMSSE with plain-python loops from the raw arrays and assert exact equality
with the module's vectorized path. The track fixtures are 20 full-length
series x ~200 days written to tmp parquet files with monkeypatched checksum
pins, so :func:`load_m5_full` runs its real validation path; the pooled-fit
smoke runs two origins on 20 series with the direct strategy and asserts
structure + run-twice byte-identity. A structural test pins the real 30,490
series panel's cardinalities (offline, skipif the cache is absent).
"""

import hashlib
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from demand_forecasting import m5_full  # noqa: E402
from demand_forecasting.evaluate import _json_safe  # noqa: E402
from demand_forecasting.m5_full import (  # noqa: E402
    FULL_PANEL_LEVEL_COUNTS,
    _seasonal_naive_forecast,
    aggregation_stack,
    apply_series_cap,
    build_aggregation,
    first_diff_scale,
    load_m5_full,
    m5_full_origins,
    official_wrmsse,
    revenue_weights,
    run_m5_full,
    wrmsse_nodes,
)

N_DAYS = 200
H = 28


# ---------------------------------------------------------------------------
# Toy frames: 3 items x 2 stores with known prices
# ---------------------------------------------------------------------------


def _toy_meta():
    """3 items (I1..I3) x 2 stores (S1, S2); states ST1/ST2, cats C1(I1,I2)/C2(I3),
    depts D1(I1)/D2(I2)/D3(I3) — enough variety to exercise every level."""
    rows = []
    for item, (cat, dept) in (("I1", ("C1", "D1")), ("I2", ("C1", "D2")), ("I3", ("C2", "D3"))):
        for store, state in (("S1", "ST1"), ("S2", "ST2")):
            rows.append((f"{item}_{store}", item, dept, cat, store, state))
    return pd.DataFrame(
        rows,
        columns=["unique_id", "item_id", "dept_id", "cat_id", "store_id", "state_id"],
    )


TOY_PRICES = {"I1_S1": 1.0, "I2_S1": 2.0, "I3_S1": 3.0, "I1_S2": 4.0, "I2_S2": 5.0, "I3_S2": 6.0}


def _toy_panel(n_days: int = 60, seed: int = 0):
    """(y_wide (6, n_days) float64, meta) — demand = per-series level + day-of-week
    bump, so first differences and node aggregations are hand-checkable."""
    ids = sorted(TOY_PRICES)
    base = {"I1_S1": 3.0, "I2_S1": 5.0, "I3_S1": 1.0, "I1_S2": 2.0, "I2_S2": 4.0, "I3_S2": 6.0}
    days = pd.date_range("2021-01-04", periods=n_days, freq="D")  # Monday start
    wide = np.zeros((len(ids), n_days))
    for i, sid in enumerate(ids):
        weekly = (np.arange(n_days) % 7 == 2).astype(float) * (i + 1)
        wide[i] = base[sid] + weekly
    return wide, _toy_meta(), days, ids


def _node_series_reference(wide: np.ndarray, meta: pd.DataFrame, level_cols: tuple[str, ...]):
    """Plain-python bottom-up aggregation — the independent reference."""
    series_ids = meta["unique_id"].tolist()
    keys = (
        ["total"]
        if not level_cols
        else sorted(meta[list(level_cols)].astype(str).agg("_".join, axis=1).unique().tolist())
    )
    out = {}
    for key in keys:
        members = []
        for i in range(len(series_ids)):
            if not level_cols:
                k = "total"
            else:
                k = "_".join(str(v) for v in meta.iloc[i][list(level_cols)])
            if k == key:
                members.append(i)
        out[key] = wide[members].sum(axis=0)
    return out


# ---------------------------------------------------------------------------
# Hand-computed hierarchy cases
# ---------------------------------------------------------------------------


def test_store_level_aggregation_hand_computed():
    wide, meta, _days, ids = _toy_panel(60)
    agg = build_aggregation(meta)
    store = agg["store"]
    assert store["node_ids"] == ["S1", "S2"]
    ref = _node_series_reference(wide, meta, ("store_id",))
    for r, key in enumerate(store["node_ids"]):
        store_of = meta.set_index("unique_id")["store_id"]
        member_cols = [j for j, sid in enumerate(ids) if store_of.loc[sid] == key]
        mat_row = store["matrix"][r].toarray().ravel()
        assert mat_row.sum() == 3  # 3 items per store
        for j, v in enumerate(mat_row):
            assert v == (1.0 if j in member_cols else 0.0)
        got = np.asarray(store["matrix"][r] @ wide).ravel()
        np.testing.assert_allclose(got, ref[key], rtol=1e-6)
    # total level = sum of everything; item_store is the identity
    total = agg["total"]
    assert total["node_ids"] == ["total"]
    np.testing.assert_allclose(
        np.asarray(total["matrix"] @ wide).ravel(), wide.sum(axis=0), rtol=1e-6
    )
    id_level = agg["item_store"]
    assert id_level["node_ids"] == sorted(ids)
    np.testing.assert_allclose(np.asarray(id_level["matrix"] @ wide), wide, rtol=1e-6)
    # level cardinalities on the toy: 1+2+2+2+3+4+6+4+6+3+6+6 = 45 nodes
    _a, node_ids, _levels, _slices = aggregation_stack(agg)
    assert len(node_ids) == 45


def test_revenue_weights_hand_computed():
    wide, meta, _days, ids = _toy_panel(60)
    agg = build_aggregation(meta)
    a_all, node_ids, _levels, _slices = aggregation_stack(agg)
    train_end = 32  # 32-day train window, 28-day scored window after it
    window = slice(train_end - 28, train_end)
    price_wide = np.zeros_like(wide)
    for i, sid in enumerate(ids):
        price_wide[i] = TOY_PRICES[sid]
    w = revenue_weights(wide, price_wide, window, a_all)

    # reference: per-node revenue over the window, normalized by the ALL-node total
    rev_all_levels = 0.0
    per_node = {}
    for name, cols in m5_full.M5_LEVELS:
        ref = _node_series_reference(wide[:, window], meta, tuple(cols))
        for key in ref:
            # node revenue: sum of member bottom revenues (price is constant per
            # bottom series -> node revenue = sum_i price_i * sum_t y_i,t)
            members = _members_of(meta, cols, key)
            rev = sum(TOY_PRICES[ids[i]] * wide[i, window].sum() for i in members)
            per_node[(name, key)] = rev
            rev_all_levels += rev
    flat_keys = [(n, k) for n, c in m5_full.M5_LEVELS for k in agg[n]["node_ids"]]
    for j, (level_name, node_key) in enumerate(flat_keys):
        expected_w = per_node[(level_name, node_key)] / rev_all_levels
        assert w[j] == pytest.approx(expected_w, rel=1e-6)
    assert w.sum() == pytest.approx(1.0)
    # hand spot-check: store S1 weight = (1*sum(I1_S1) + 2*sum(I2_S1) + 3*sum(I3_S1))
    # over the window, divided by 12 x panel revenue (12 levels, equal totals)
    panel_rev = sum(TOY_PRICES[sid] * wide[i, window].sum() for i, sid in enumerate(ids))
    s1_rev = (
        TOY_PRICES["I1_S1"] * wide[ids.index("I1_S1"), window].sum()
        + TOY_PRICES["I2_S1"] * wide[ids.index("I2_S1"), window].sum()
        + TOY_PRICES["I3_S1"] * wide[ids.index("I3_S1"), window].sum()
    )
    s1_w = w[node_ids.index("S1")]
    assert s1_w == pytest.approx(s1_rev / (12 * panel_rev), rel=1e-6)


def _members_of(meta: pd.DataFrame, cols: tuple[str, ...], key: str) -> list[int]:
    if not cols:
        return list(range(len(meta)))
    out = []
    for i in range(len(meta)):
        if "_".join(str(v) for v in meta.iloc[i][list(cols)]) == key:
            out.append(i)
    return out


def test_official_wrmsse_hand_computed():
    """Full end-to-end score on the toy: pred = 0.5*actual + 1 recomputed with
    plain loops from the raw arrays."""
    wide, meta, _days, ids = _toy_panel(60)
    train_end = 32
    agg = build_aggregation(meta)
    a_all, _node_ids, _levels, _level_slices = aggregation_stack(agg)
    pred = wide[:, train_end : train_end + H] * 0.5 + 1.0

    train_nodes = np.asarray(a_all @ wide[:, :train_end])
    actual_nodes = np.asarray(a_all @ wide[:, train_end : train_end + H])
    scale = first_diff_scale(train_nodes)
    price_wide = np.array([[TOY_PRICES[sid]] * wide.shape[1] for sid in ids])
    w = revenue_weights(wide, price_wide, slice(train_end - 28, train_end), a_all)
    score, excluded = official_wrmsse(pred, actual_nodes, scale, w, a_all)

    # ---- independent reference ----
    node_keys = [(n, k) for n, c in m5_full.M5_LEVELS for k in agg[n]["node_ids"]]
    expected_num = 0.0
    expected_den = 0.0
    for level_name, key in node_keys:
        members = _members_of(meta, dict(m5_full.M5_LEVELS)[level_name], key)
        node_train = wide[members][:, :train_end].sum(axis=0)
        node_scored = wide[members][:, train_end : train_end + H].sum(axis=0)
        node_pred = pred[members].sum(axis=0)
        diffs = np.diff(node_train)
        denom = float(np.mean(diffs * diffs)) if node_train.size >= 2 else float("nan")
        if not np.isfinite(denom) or denom <= 0:
            continue
        rmsse_j = float(np.sqrt(np.mean((node_pred - node_scored) ** 2) / denom))
        # weight: node revenue over the preceding 28 days / all-node revenue
        rev_j = sum(TOY_PRICES[ids[i]] * wide[i, train_end - 28 : train_end].sum() for i in members)
        rev_all = 0.0
        for _ln, _key in node_keys:
            _m = _members_of(meta, dict(m5_full.M5_LEVELS)[_ln], _key)
            rev_all += sum(
                TOY_PRICES[ids[i]] * wide[i, train_end - 28 : train_end].sum() for i in _m
            )
        w_j = rev_j / rev_all
        expected_num += w_j * rmsse_j
        expected_den += w_j
    expected = expected_num / expected_den
    assert excluded == 0  # every toy node has non-constant train history
    assert score == pytest.approx(expected, rel=1e-5)

    # the components also match their hand values
    err_nodes = np.asarray(a_all @ pred) - actual_nodes
    rmsse, _wv = wrmsse_nodes(err_nodes, scale, w)
    # total node is the first node: check its rmsse by hand
    total_train = wide[:, :train_end].sum(axis=0)
    total_scored = wide[:, train_end : train_end + H].sum(axis=0)
    total_pred = pred.sum(axis=0)
    d = np.diff(total_train)
    denom = float(np.mean(d * d))
    hand = float(np.sqrt(np.mean((total_pred - total_scored) ** 2) / denom))
    assert rmsse[0] == pytest.approx(hand, rel=1e-5)


def test_seasonal_naive_vectorized():
    rng = np.random.default_rng(1)
    wide = rng.integers(0, 9, size=(4, 40)).astype(float)
    fc = _seasonal_naive_forecast(wide, H)
    assert fc.shape == (4, H)
    for k in range(H):
        np.testing.assert_array_equal(fc[:, k], wide[:, 33 + (k % 7)])


def test_m5_full_origins_end_anchored():
    origins = m5_full_origins(1969, 10, H, 1096, 7)
    assert origins[-1] == 1969 - H - 1  # the scored window is the LAST 28 days
    assert origins[0] == origins[-1] - 7 * 9
    assert len(origins) == 10
    with pytest.raises(ValueError, match="panel too short"):
        m5_full_origins(100, 2, H, 1096, 7)
    with pytest.raises(ValueError, match="not enough history"):
        m5_full_origins(1150, 10, H, 1096, 7)  # first origin would be day 1058 < 1095


# ---------------------------------------------------------------------------
# Loader checksum enforcement (monkeypatched pins on tiny frames)
# ---------------------------------------------------------------------------


def _write_tiny_full(tmp_path: Path, ydf: pd.DataFrame, xdf: pd.DataFrame, sdf: pd.DataFrame):
    """Tiny full-panel layout: m5.zip + .cache parquets, with pinned checksums."""
    raw = tmp_path / "raw"
    (raw / "m5" / "datasets").mkdir(parents=True)
    (raw / ".cache" / "m5" / "m5").mkdir(parents=True)
    (raw / "m5" / "datasets" / "m5.zip").write_bytes(b"toy zip")
    checksums = {"m5/datasets/m5.zip": hashlib.sha256(b"toy zip").hexdigest()}
    for name, frame in (("Y_df", ydf), ("X_df", xdf), ("S_df", sdf)):
        path = raw / ".cache" / "m5" / "m5" / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        checksums[f".cache/m5/m5/{name}.parquet"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return raw, checksums


def _track_frames(n_series: int = 20, n_days: int = N_DAYS, seed: int = 0):
    """20 full-length series (10 items x 2 stores) with weekly demand + prices."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2020-06-01", periods=n_days, freq="D")
    items = [f"ITEM_{i:02d}" for i in range(n_series // 2)]
    stores = ["S1", "S2"]
    cats = {item: ("C1" if i < n_series // 4 else "C2") for i, item in enumerate(items)}
    depts = {item: (f"D{1 + (i % 4)}") for i, item in enumerate(items)}
    recs, xrecs, srecs = [], [], []
    for item in items:
        for store in stores:
            sid = f"{item}_{store}"
            state = "ST1" if store == "S1" else "ST2"
            base = 2.0 + 1.5 * (int(item[-2:]) % 5)
            weekly = 2.0 * np.sin(np.arange(n_days) * 2 * np.pi / 7)
            y = np.maximum(rng.poisson(base, n_days).astype(float) + weekly, 0.0)
            if int(item[-2:]) % 3 == 0:
                y = np.where(rng.random(n_days) < 0.35, y * 3.0, 0.0)  # intermittent
            price = float(np.round(1.0 + 0.25 * (int(item[-2:]) % 6), 2))
            for d, v in zip(days, y, strict=True):
                recs.append((sid, d, float(v)))
            for d in days:
                xrecs.append(
                    (
                        sid,
                        d,
                        "Easter" if d.day == 15 else None,
                        "Religious" if d.day == 15 else None,
                        None,
                        None,
                        1 if d.day % 10 < 5 else 0,
                        0,
                        0,
                        price,
                    )
                )
            srecs.append((sid, item, depts[item], cats[item], store, state))
    ydf = pd.DataFrame(recs, columns=["unique_id", "ds", "y"])
    xdf = pd.DataFrame(
        xrecs,
        columns=[
            "unique_id",
            "ds",
            "event_name_1",
            "event_type_1",
            "event_name_2",
            "event_type_2",
            "snap_CA",
            "snap_TX",
            "snap_WI",
            "sell_price",
        ],
    )
    sdf = pd.DataFrame(
        srecs,
        columns=["unique_id", "item_id", "dept_id", "cat_id", "store_id", "state_id"],
    )
    return ydf, xdf, sdf


def test_loader_checksum_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    y2, _x, s2 = load_m5_full(raw)
    assert len(s2) == 20 and len(y2) == 20 * N_DAYS
    # drift one cache file: rewrite Y -> loud failure
    y3 = y.copy()
    y3.loc[0, "y"] = 999.0
    y3.to_parquet(raw / ".cache" / "m5" / "m5" / "Y_df.parquet", index=False)
    with pytest.raises(ValueError, match="checksum"):
        load_m5_full(raw)


# ---------------------------------------------------------------------------
# Tiny track: pooled-fit smoke, structure + run-twice byte-identity
# ---------------------------------------------------------------------------


def _dump(result) -> str:
    return json.dumps(_json_safe(result.metrics), sort_keys=True, allow_nan=False)


def _track_kwargs(tmp_path: Path):
    return dict(
        n_origins=2,
        pooled_strategy="direct",
        n_estimators=5,
        min_train=140,
        params_path=tmp_path / "no_params.yaml",  # defaults; n_estimators override wins
    )


def test_tiny_track_run_twice_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    r1 = run_m5_full(raw, **_track_kwargs(tmp_path))
    r2 = run_m5_full(raw, **_track_kwargs(tmp_path))
    assert _dump(r1) == _dump(r2)
    # structural invariants
    assert r1.metrics["protocol"] == "m5_full_v1"
    assert r1.metrics["pooled_strategy"] == "direct"
    assert r1.metrics["origins"]["test"] == r1.metrics["origins"]["dates"][-1:]
    assert len(r1.metrics["origins"]["dates"]) == 2
    assert r1.metrics["hierarchy"]["n_nodes_total"] == 85  # 1+2+2+2+4+4+8+4+8+10+20+20
    test_block = r1.metrics["test"]
    for cand in (
        "seasonal_naive",
        "lgbm",
        "lgbm_tweedie",
        "lgbm_pool_store",
        "lgbm_pool_storecat",
        "lgbm_pool_dept",
        "auto_ets",
        "convex_ensemble",
    ):
        entry = test_block[cand]
        for key in (
            "official_wrmsse",
            "per_level_wrmsse",
            "bottom_wape",
            "bias",
            "zero_day_accuracy",
        ):
            assert key in entry, f"{cand}: missing {key}"
        assert entry["official_wrmsse"] == entry["official_wrmsse"]  # finite
        assert entry["official_wrmsse"] > 0
        assert set(entry["per_level_wrmsse"]) == set(r1.metrics["hierarchy"]["levels"])
    # ensemble: 3 members, simplex weights
    ens = r1.metrics["ensemble"]
    assert len(ens["members"]) == len(ens["weights"]) == 3
    assert sum(ens["weights"]) == pytest.approx(1.0, abs=1e-9)
    assert set(ens["selection_screen"]) == set(ens["pool"])
    # classes cover all series
    counts = r1.metrics["classes"]["counts"]
    assert counts["dense"] + counts["intermittent"] == 20
    # selection stability rides every candidate
    for cand in r1.metrics["candidates"]:
        assert r1.metrics["selection"][cand]["stability"] >= 0.0
    # runtime recorded per candidate per origin (metadata, not metrics —
    # wall-clock values must not enter the byte-identity block)
    assert set(r1.metadata["runtime_seconds_per_candidate_origin"]) == set(r1.metrics["candidates"])


def test_tiny_track_recursive_pooled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    kwargs = _track_kwargs(tmp_path) | {"pooled_strategy": "recursive"}
    r1 = run_m5_full(raw, **kwargs)
    r2 = run_m5_full(raw, **kwargs)
    assert _dump(r1) == _dump(r2)
    assert r1.metrics["pooled_strategy"] == "recursive"
    assert r1.metrics["test"]["lgbm_pool_store"]["official_wrmsse"] > 0


def test_ladder_cap_deterministic():
    y, x, s = _track_frames()
    _y1, _x1, s1 = apply_series_cap(y, x, s, cap=10)  # top-1 item x 2 stores
    _y2, _x2, s2 = apply_series_cap(y, x, s, cap=10)
    assert s1["unique_id"].tolist() == s2["unique_id"].tolist()
    assert len(s1) == 2  # one item contributes both store series
    assert s1["item_id"].nunique() == 1
    # cap larger than the panel keeps everything
    _y3, _x3, s3 = apply_series_cap(y, x, s, cap=10_000)
    assert len(s3) == 20


# ---------------------------------------------------------------------------
# Real pinned panel: structural pins (offline; skipif the cache is absent)
# ---------------------------------------------------------------------------

REAL_RAW = Path(__file__).resolve().parent.parent / "data_m5" / "raw"


@pytest.mark.skipif(
    not (REAL_RAW / ".cache" / "m5" / "m5" / "Y_df.parquet").exists(),
    reason="pinned M5 full-panel cache not present",
)
def test_real_full_panel_structure():
    y, _x, s = load_m5_full(REAL_RAW)
    assert y["unique_id"].nunique() == 30_490
    assert y["ds"].nunique() == 1969
    assert str(y["ds"].max().date()) == "2016-06-19"  # includes the eval window
    assert str(y["ds"].min().date()) == "2011-01-29"
    s_sorted = s.drop_duplicates("unique_id").sort_values("unique_id", ignore_index=True)
    agg = build_aggregation(s_sorted)
    counts = {name: len(agg[name]["node_ids"]) for name, _ in m5_full.M5_LEVELS}
    assert counts == FULL_PANEL_LEVEL_COUNTS
    _a, node_ids, _levels, _slices = aggregation_stack(agg)
    assert len(node_ids) == 42_840
    # the scored-once window is exactly the last 28 days of the panel
    origins = m5_full_origins(1969, 10, H, 1096, 7)
    assert origins[-1] == 1940
    dates = np.sort(y["ds"].unique())
    assert str(pd.Timestamp(dates[1941]).date()) == "2016-05-23"
    assert str(pd.Timestamp(dates[1968]).date()) == "2016-06-19"
    # every series has >= MIN_SERIES_HISTORY_DAYS days at the first origin
    first = pd.Timestamp(dates[origins[0]])
    min_hist = (first - y.groupby("unique_id")["ds"].min().max()).days
    assert min_hist >= m5_full.MIN_SERIES_HISTORY_DAYS
