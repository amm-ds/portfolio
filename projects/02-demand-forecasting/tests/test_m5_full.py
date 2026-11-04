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
    PEAK_CANDIDATE,
    PEAK_WEIGHTS,
    ROUTED_CANDIDATE,
    _erratic_gate,
    _peak_train_weights,
    _seasonal_naive_forecast,
    _wrmsse_delta_bootstrap,
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
from demand_forecasting.multistep_models import peak_sample_weights  # noqa: E402

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


# ---------------------------------------------------------------------------
# Wave-32: batch AutoETS index regression (the full-panel "index 30490 is out
# of bounds" failure — pre-fix the per-series fallback masked it at every scale)
# ---------------------------------------------------------------------------


def _tripwire_on_batch_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the documented per-series fallback FAIL the test if it triggers —
    the regression is the fallback firing at all (pre-fix it fired at every
    origin, boundary-sized panels included)."""
    real_warning = m5_full.logger.warning

    def _guarded(msg: object, *args: object, **kwargs: object) -> None:
        text = str(msg)
        if "batch auto_ets failed" in text or "per-series fallback" in text:
            detail = text % args if args else text
            raise AssertionError(f"batch auto_ets must not fall back: {detail}")
        real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(m5_full.logger, "warning", _guarded)


class _FakeStatsForecast:
    """Mimics statsforecast 2.x ``fit_predict``: a LONG frame with one row per
    (series, horizon step), series-major blocks of ``h`` rows. Deliberately
    emits uids in REVERSED order (the real library sorts them; the reorder to
    the caller's ``series_ids`` order must not assume it) so a broken reorder
    fails loudly instead of passing by luck."""

    def __init__(self, models: object, freq: str, n_jobs: int = 1) -> None:
        self.freq = freq

    def fit_predict(
        self, h: int, df: pd.DataFrame, id_col: str, time_col: str, target_col: str
    ) -> pd.DataFrame:
        uids = sorted(df[id_col].unique(), reverse=True)  # NOT the caller's order
        days = pd.date_range("2016-05-23", periods=h, freq="D")
        fc_pos = {u: i for i, u in enumerate(uids)}
        # deterministic value encoding its (fc block, step) so ordering bugs show
        vals = np.array([fc_pos[u] * 1000.0 + k for u in uids for k in range(h)], dtype=float)
        return pd.DataFrame(
            {
                "unique_id": np.repeat(uids, h),
                "ds": np.tile(days, len(uids)),
                "auto_ets": vals,
            }
        )


def test_auto_ets_batch_boundary_fixture(monkeypatch: pytest.MonkeyPatch):
    """The exact full-panel size, mocked library: pre-fix this raised
    IndexError('index 30490 is out of bounds for axis 0 with size 30490') at
    every origin and silently degraded to the per-series fallback."""
    import statsforecast

    n_series = 30_490  # the boundary size from the overnight log
    uids = [f"FULL_{i:05d}" for i in range(n_series)]
    days = pd.date_range("2016-04-01", periods=3, freq="D")
    train = pd.DataFrame(
        {
            "unique_id": np.repeat(uids, len(days)),
            "ds": np.tile(days, n_series),
            "y": 1.0,
        }
    )
    monkeypatch.setattr(statsforecast, "StatsForecast", _FakeStatsForecast)
    _tripwire_on_batch_fallback(monkeypatch)

    mat = m5_full._auto_ets_forecast(train, uids, H, n_jobs=1)

    assert mat.shape == (n_series, H)
    # uids arrive reversed from the fake; the caller's order must be restored:
    # series i sits in fc block (n_series - 1 - i) of the reversed emission.
    for i in (0, 1, 123, n_series // 2, n_series - 2, n_series - 1):
        expected = (n_series - 1 - i) * 1000.0 + np.arange(H, dtype=float)
        np.testing.assert_array_equal(mat[i], expected)
    assert not np.isnan(mat).any()


def test_auto_ets_batch_real_statsforecast_matches_per_series():
    """Contract test against the REAL statsforecast (output format is a library
    property): the batch matrix must equal per-series fits one uid at a time,
    in the caller's (here reverse-sorted) series order."""
    rng = np.random.default_rng(7)
    n_series, t = 6, 90
    days = pd.date_range("2021-01-04", periods=t, freq="D")
    recs = []
    for i in range(n_series):
        level = float(rng.integers(1, 6))
        y = rng.poisson(level, t).astype(float) + (np.arange(t) % 7 == i % 7) * i
        recs.extend((f"r{i}", d, v) for d, v in zip(days, y, strict=True))
    train = pd.DataFrame(recs, columns=["unique_id", "ds", "y"])
    series_ids = sorted(train["unique_id"].unique(), reverse=True)  # unordered on purpose

    from statsforecast import StatsForecast
    from statsforecast.models import AutoETS

    mat = m5_full._auto_ets_forecast(train, series_ids, H, n_jobs=1)
    assert mat.shape == (len(series_ids), H)

    for pos, sid in ((0, series_ids[0]), (3, series_ids[3]), (5, series_ids[-1])):
        one = train[train["unique_id"] == sid]
        ref = StatsForecast(models=[AutoETS(season_length=7)], freq="D", n_jobs=1).fit_predict(
            h=H, df=one, id_col="unique_id", time_col="ds", target_col="y"
        )
        np.testing.assert_allclose(
            mat[pos], ref["AutoETS"].to_numpy(dtype=float), rtol=1e-9, atol=1e-9
        )


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


# ---------------------------------------------------------------------------
# Wave-33 erratic-quadrant refinement: weight rule, gate math, byte identity,
# and the no-test-read property
# ---------------------------------------------------------------------------


def test_peak_train_weights_hand_computed():
    """The ported top-decile rule on a long frame, incl. parity with the
    multistep track's peak_sample_weights on a layout both express."""
    # series A: positives 1..10 (np.quantile(0.9) of positives = 9.1 -> only
    # y=10 is up-weighted); zeros stay at 1. series B: all zeros -> all 1.
    y_a = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    y_b = np.zeros(11)
    y = np.concatenate([y_a, y_b])
    uids = np.array(["A"] * 11 + ["B"] * 11)
    w = _peak_train_weights(y, uids, 3.0)
    assert w.shape == y.shape
    assert w[y == 10.0][0] == 3.0
    assert w[(y > 0) & (y < 10.0)].sum() == 9.0  # nine positives at weight 1
    assert w[y == 0.0].sum() == len(y_a[y_a == 0.0]) + 11.0  # zeros + series B at 1
    # weight 2 changes nothing about WHICH rows fire
    w2 = _peak_train_weights(y, uids, 2.0)
    assert np.array_equal(w2 == 2.0, w == 3.0)

    # parity with the multistep helper: series-minor layout, two series
    # (flat index r*2 + i is series i at window-row r — np.tile, not repeat)
    rng = np.random.default_rng(7)
    block = rng.poisson(2.0, size=(13, 2)).astype(float)
    block[3, 1] = 30.0  # force an unambiguous top-decile spike in series 1
    uids2 = np.tile(["S0", "S1"], 13)
    y_long = block.reshape(-1)  # row r of series i sits at r*2 + i
    w_long = _peak_train_weights(y_long, uids2, 2.5)
    w_ref = peak_sample_weights(y_long.copy(), 2, 2.5)
    np.testing.assert_allclose(w_long, w_ref)


def test_erratic_gate_branches():
    adopted = _erratic_gate(
        win_rate_champion=0.40, win_rate_routed=0.44, wrmsse_delta=0.0005, noise_tol=0.002
    )
    assert adopted["adopted"] is True
    assert adopted["checks"]["erratic_win_rate_vs_floor"]["ok"] is True
    # win rate does not improve -> reject even when WRMSSE is fine
    no_win = _erratic_gate(
        win_rate_champion=0.44, win_rate_routed=0.40, wrmsse_delta=-0.001, noise_tol=0.002
    )
    assert no_win["adopted"] is False
    assert no_win["checks"]["erratic_win_rate_vs_floor"]["ok"] is False
    # WRMSSE regresses beyond the noise band -> reject even when win improves
    regress = _erratic_gate(
        win_rate_champion=0.40, win_rate_routed=0.50, wrmsse_delta=0.01, noise_tol=0.002
    )
    assert regress["adopted"] is False
    assert regress["checks"]["official_wrmsse_delta_routed_minus_champion"]["ok"] is False
    # no erratic series in the window -> cannot adopt
    absent = _erratic_gate(
        win_rate_champion=None, win_rate_routed=None, wrmsse_delta=0.0, noise_tol=0.002
    )
    assert absent["adopted"] is False


def test_wrmsse_delta_bootstrap_toy():
    """Identical forecasts give an all-zero delta; the paired draw is
    deterministic under the seed; the point estimate matches the direct score."""
    wide, meta, _days, ids = _toy_panel(60)
    agg = build_aggregation(meta)
    a_all, _node_ids, _levels, _slices = aggregation_stack(agg)
    o = 40
    train_nodes = np.asarray(a_all @ wide[:, :o])
    actual_nodes = np.asarray(a_all @ wide[:, o : o + 4])
    scale = first_diff_scale(train_nodes)
    price = np.array([TOY_PRICES[sid] for sid in ids])
    price_wide = np.tile(price[:, None], (1, 60))
    w = revenue_weights(wide, price_wide, slice(o - 3, o + 1), a_all)
    ctx = {"actual_nodes": actual_nodes, "scale": scale, "weights": w}
    pred = wide[:, o : o + 4] * 1.01
    same = _wrmsse_delta_bootstrap(pred, pred.copy(), ctx, a_all, n_boot=50, seed=1)
    assert same["delta_point"] == 0.0
    assert same["ci95"] == [0.0, 0.0]
    shifted = wide[:, o : o + 4] * 1.03
    b1 = _wrmsse_delta_bootstrap(shifted, pred, ctx, a_all, n_boot=50, seed=1)
    b2 = _wrmsse_delta_bootstrap(shifted, pred, ctx, a_all, n_boot=50, seed=1)
    assert b1 == b2  # deterministic under the seed
    assert b1["delta_point"] != 0.0
    assert b1["noise_tol"] >= 0.0


def _refinement_selection_fields(metrics: dict) -> dict:
    """The fields the no-test-read property pins (all selection-derived)."""
    ref = metrics["erratic_refinement"]
    return {
        "chosen": ref["peak_weight_choice"]["chosen"],
        "n_routed": ref["routing"]["n_routed_to_peak"],
        "selection_wrmsse": ref["selection_per_origin_official_wrmsse"],
        "members": metrics["ensemble"]["members"],
        "weights": metrics["ensemble"]["weights"],
    }


def test_tiny_track_refinement_structure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The erratic_refinement block rides every run: weight chosen on the
    screen, routing confined to the erratic class, gate verdict consistent
    with its own inputs, and run-twice byte identity."""
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    r1 = run_m5_full(raw, **_track_kwargs(tmp_path))
    r2 = run_m5_full(raw, **_track_kwargs(tmp_path))
    assert _dump(r1) == _dump(r2)
    ref = r1.metrics["erratic_refinement"]
    assert ref["peak_candidate"] == PEAK_CANDIDATE
    assert ref["routed_candidate"] == ROUTED_CANDIDATE
    assert ref["peak_weight_choice"]["chosen"] in list(PEAK_WEIGHTS)
    assert set(ref["peak_weight_choice"]["selection_screen"]) == {"2.0", "3.0"}
    n_erratic = ref["n_erratic_series"]
    assert 0 <= ref["routing"]["n_routed_to_peak"] <= n_erratic
    wr = ref["test"]["official_wrmsse"]
    assert wr["convex_ensemble"] > 0 and wr[PEAK_CANDIDATE] > 0 and wr[ROUTED_CANDIDATE] > 0
    rates = {k: v["win_rate"] for k, v in ref["test"]["erratic_win_rate_vs_floor"].items()}
    if n_erratic:
        assert all(r is not None for r in rates.values())
    # the committed verdict recomputes from the block's own numbers
    gate = ref["adoption_gate"]
    expected = _erratic_gate(
        win_rate_champion=rates["convex_ensemble"],
        win_rate_routed=rates[ROUTED_CANDIDATE],
        wrmsse_delta=wr[ROUTED_CANDIDATE] - wr["convex_ensemble"],
        noise_tol=ref["wrmsse_delta_bootstrap_routed_vs_champion"]["noise_tol"],
    )
    assert gate["adopted"] == expected["adopted"]
    # the headline candidate set is untouched by the refinement block
    assert r1.metrics["candidates"] == [
        "seasonal_naive",
        "lgbm",
        "lgbm_tweedie",
        "lgbm_pool_store",
        "lgbm_pool_storecat",
        "lgbm_pool_dept",
        "auto_ets",
        "convex_ensemble",
    ]


def test_refinement_selection_reads_no_test_actuals(tmp_path: Path, monkeypatch):
    """Property: rolling the scored window's actuals (the last 28 days — past
    every origin's training cut) leaves every selection-derived field
    unchanged while the headline test scores move."""
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    r1 = run_m5_full(raw, **_track_kwargs(tmp_path))

    origins = m5_full_origins(N_DAYS, 2, H, 140, 7)
    o_test = origins[-1]
    dates_arr = pd.date_range("2020-06-01", periods=N_DAYS, freq="D")
    # the selection origin scores up to (o_test - 7) + H; only the LAST 7 days
    # are scored by the test origin alone — rolling them cannot touch any fit
    # (every origin trains earlier) or any selection-origin score
    first_test_only = (o_test - 7) + H + 1
    test_only = dates_arr[first_test_only:]
    y2 = y.copy()
    test_rows = y2["ds"].isin(test_only)
    rolled = (
        y2.loc[test_rows]
        .groupby("unique_id")["y"]
        .transform(lambda v: np.roll(v.to_numpy(dtype=float), 3))
    )
    y2.loc[test_rows, "y"] = rolled.to_numpy(dtype=float)
    raw2 = tmp_path / "raw2"
    (raw2 / "m5" / "datasets").mkdir(parents=True)
    (raw2 / ".cache" / "m5" / "m5").mkdir(parents=True)
    (raw2 / "m5" / "datasets" / "m5.zip").write_bytes(b"toy zip")
    checksums2 = {"m5/datasets/m5.zip": hashlib.sha256(b"toy zip").hexdigest()}
    for name, frame in (("Y_df", y2), ("X_df", x), ("S_df", s)):
        path = raw2 / ".cache" / "m5" / "m5" / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        checksums2[f".cache/m5/m5/{name}.parquet"] = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums2)
    r2 = run_m5_full(raw2, **_track_kwargs(tmp_path))

    assert _refinement_selection_fields(r1.metrics) == _refinement_selection_fields(r2.metrics)
    # the perturbation actually reached the scored window: every stored
    # forecast is identical, so any headline test movement proves actuals drive
    # the test scores, not the fits
    t1 = {c: r1.metrics["test"][c]["official_wrmsse"] for c in r1.metrics["candidates"]}
    t2 = {c: r2.metrics["test"][c]["official_wrmsse"] for c in r2.metrics["candidates"]}
    assert t1 != t2


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
# Wave-32: catalog dump mode (test origin only, committed-weights blend)
# ---------------------------------------------------------------------------


def test_catalog_selection_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Deterministic two-half rule: counts, disjointness, cell balance, and
    the bottom half picking the hardest intermittent series first."""
    from demand_forecasting.m5_full_catalog import select_catalog_ids

    y, x, s = _track_frames(seed=1)
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    panel = m5_full._prepare_panel(
        raw, series_cap=None, seed=0, params_path=tmp_path / "no_params.yaml", n_estimators=5
    )
    o = m5_full_origins(panel.n_dates, 1, H, 140, 7)[-1]
    chosen, descr = select_catalog_ids(panel, o, catalog_size=12)
    assert len(chosen) == len(set(chosen)) == 12  # disjoint halves
    chosen2, _ = select_catalog_ids(panel, o, catalog_size=12)
    assert chosen == chosen2  # deterministic
    halves = {}
    for i in chosen:
        halves[descr[i]["half"]] = halves.get(descr[i]["half"], 0) + 1
    assert halves == {"top_units": 6, "bottom_intermittency": 6}
    # 2 stores x 2 cats = 4 cells; each half round-robins 6 picks over 4
    # cells: 2 cells twice, 2 cells once — per half
    cells = sorted({f"{descr[i]['store']}_{descr[i]['cat_id']}" for i in chosen})
    assert len(cells) == 4
    for half in ("top_units", "bottom_intermittency"):
        counts = sorted(
            sum(
                1
                for i in chosen
                if descr[i]["half"] == half and f"{descr[i]['store']}_{descr[i]['cat_id']}" == c
            )
            for c in cells
        )
        assert counts == [1, 1, 2, 2], f"{half}: {counts}"
    # the halves are cell-prefixes of their rankings: within each cell, no
    # un-picked series may rank AHEAD of a picked one (recomputed here
    # independently from the raw panel)
    from demand_forecasting.intermittent import classify_demand
    from demand_forecasting.m5_track import _series_train_history

    hist = _series_train_history(panel.y_all, panel.series_ids, pd.Timestamp(panel.dates[o]))
    units = panel.y_wide[:, -H:].sum(axis=1)

    def harder(q: int, p: int) -> bool:
        cq = classify_demand(hist[panel.series_ids[q]])
        cp = classify_demand(hist[panel.series_ids[p]])
        return (cq["adi"], min(cq["cv2"], float("inf"))) > (
            cp["adi"],
            min(cp["cv2"], float("inf")),
        )

    for i in chosen:
        cell = f"{descr[i]['store']}_{descr[i]['cat_id']}"
        for j in range(panel.n_series):
            same_cell = (
                f"{panel.s_meta['store_id'].loc[panel.series_ids[j]]}_"
                f"{panel.s_meta['cat_id'].loc[panel.series_ids[j]]}"
            ) == cell
            if j in chosen or not same_cell:
                continue
            if descr[i]["half"] == "top_units":
                assert units[j] <= units[i] + 1e-9, f"{panel.series_ids[j]} is bigger but unpicked"
            else:
                assert not harder(j, i), f"{panel.series_ids[j]} is harder but unpicked"
    # descriptors carry the ranking provenance
    for i in chosen:
        assert descr[i]["units_rank"] >= 0 and descr[i]["intermittency_rank"] >= 0
        assert isinstance(descr[i]["adi"], float) and isinstance(descr[i]["cv2"], (float, str))


def test_load_committed_ensemble_guards(tmp_path: Path):
    from demand_forecasting.m5_full_catalog import load_committed_ensemble

    missing = tmp_path / "metrics.json"
    with pytest.raises(FileNotFoundError):
        load_committed_ensemble(missing)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"protocol": "m5_direct_v1", "ensemble": {}}))
    with pytest.raises(ValueError, match="protocol"):
        load_committed_ensemble(bad)
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps(
            {
                "protocol": "m5_full_v1",
                "ensemble": {"members": ["lgbm", "auto_ets"], "weights": [0.7, 0.3]},
            }
        )
    )
    assert load_committed_ensemble(good) == (["lgbm", "auto_ets"], [0.7, 0.3])


def test_catalog_mode_tiny(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """End-to-end catalog run on the tiny panel: schema, committed-weights
    blend, parquet round-trip, meta block, determinism."""
    from demand_forecasting.m5_full_catalog import (
        CATALOG_META_NAME,
        run_m5_full_catalog,
    )

    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    track_kwargs = dict(min_train=140, n_estimators=5, params_path=tmp_path / "no_params.yaml")
    committed = run_m5_full(raw, n_origins=2, pooled_strategy="recursive", **track_kwargs)
    reports = tmp_path / "reports"
    reports.mkdir()
    metrics_path = reports / "metrics.json"
    metrics_path.write_text(json.dumps(_json_safe(committed.metrics)))

    out = reports / "catalog_forecasts.parquet"
    res1 = run_m5_full_catalog(
        raw,
        out,
        metrics_path=metrics_path,
        catalog_size=12,
        series_cap=None,
        pooled_strategy="recursive",
        **track_kwargs,
    )
    frame = res1.frame
    expected_cols = [
        "unique_id",
        "ds",
        "actual",
        *m5_full.CANDIDATES,
        "band_lo",
        "band_hi",
    ]
    assert list(frame.columns) == expected_cols
    assert len(frame) == 12 * H
    assert frame["unique_id"].nunique() == 12
    assert frame.groupby("unique_id").size().eq(H).all()

    meta = res1.meta
    assert meta["protocol"] == "m5_full_v1"
    assert meta["catalog_size"] == 12
    assert len(meta["series"]) == 12
    assert meta["weights_source"] == str(metrics_path)
    assert meta["runtime_seconds"] > 0
    assert set(meta["runtime_seconds_per_candidate"]) == set(m5_full.CANDIDATES) - {
        "seasonal_naive",
        "convex_ensemble",
    }

    # weights reuse, NOT re-selection: the persisted blend is exactly the
    # committed members x committed weights
    members = meta["ensemble"]["members"]
    weights = meta["ensemble"]["weights"]
    assert members == committed.metrics["ensemble"]["members"]
    np.testing.assert_allclose(sum(weights), 1.0, atol=1e-9)
    blend = np.zeros(len(frame))
    for w, m in zip(weights, members, strict=True):
        blend += w * frame[m].to_numpy(dtype=float)
    np.testing.assert_allclose(frame["convex_ensemble"].to_numpy(dtype=float), blend, atol=1e-9)
    # the band is the member envelope
    lo = np.minimum.reduce([frame[m].to_numpy(dtype=float) for m in members])
    hi = np.maximum.reduce([frame[m].to_numpy(dtype=float) for m in members])
    np.testing.assert_allclose(frame["band_lo"].to_numpy(dtype=float), lo, atol=1e-9)
    np.testing.assert_allclose(frame["band_hi"].to_numpy(dtype=float), hi, atol=1e-9)

    # self-check results are recorded and tight
    check = meta["self_check"]
    assert check["ensemble_blend_max_abs_drift"] <= 1e-9
    assert check["actuals_max_abs_drift"] <= 1e-9
    assert check["ensemble_catalog_wape"] > 0

    # artifacts on disk: parquet round-trips + catalog_meta.json
    import pyarrow.parquet as pq

    reread = pq.read_table(out).to_pandas()
    pd.testing.assert_frame_equal(frame, reread)
    meta_on_disk = json.loads((reports / CATALOG_META_NAME).read_text())
    assert meta_on_disk["catalog_size"] == 12
    assert meta_on_disk["ensemble"]["members"] == members

    # determinism: a second run produces the identical frame
    res2 = run_m5_full_catalog(
        raw,
        out,
        metrics_path=metrics_path,
        catalog_size=12,
        series_cap=None,
        pooled_strategy="recursive",
        **track_kwargs,
    )
    pd.testing.assert_frame_equal(frame, res2.frame)
    assert [d["unique_id"] for d in res2.meta["series"]] == [d["unique_id"] for d in meta["series"]]


def test_catalog_mode_rejects_wrong_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from demand_forecasting.m5_full_catalog import run_m5_full_catalog

    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp_path, y, x, s)
    monkeypatch.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"protocol": "m5_direct_v1"}))
    with pytest.raises(ValueError, match="protocol"):
        run_m5_full_catalog(
            raw,
            tmp_path / "catalog.parquet",
            metrics_path=metrics_path,
            catalog_size=4,
            series_cap=None,
            min_train=140,
            n_estimators=5,
            params_path=tmp_path / "no_params.yaml",
        )


# ---------------------------------------------------------------------------
# Real pinned panel: structural pins (offline; skipif the cache is absent)
# ---------------------------------------------------------------------------

REAL_RAW = Path(__file__).resolve().parent.parent / "data_m5" / "raw"

REAL_RAW_FILES = (
    REAL_RAW / "m5" / "datasets" / "m5.zip",
    REAL_RAW / ".cache" / "m5" / "m5" / "Y_df.parquet",
    REAL_RAW / ".cache" / "m5" / "m5" / "X_df.parquet",
    REAL_RAW / ".cache" / "m5" / "m5" / "S_df.parquet",
)


@pytest.mark.skipif(
    not all(path.exists() for path in REAL_RAW_FILES),
    reason="pinned M5 full-panel cache not present (fresh clone without DVC pull)",
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
