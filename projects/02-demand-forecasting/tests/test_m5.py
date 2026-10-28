"""M5 track tests: hand-computed tiny cases + a real-subset structural smoke.

The tiny fixtures are 3 full-length series x ~150 days written to tmp parquet
files with monkeypatched checksum pins, so :func:`load_m5_subset` runs its
real validation path. The real-data smoke subsets the committed M5 panel
deterministically (sorted unique_id, first 20), runs two origins and asserts
structure + run-twice byte-identity; it reports (logs) whether lgbm beats the
naive at the total level but deliberately does NOT assert the win — the
honesty rule: measured numbers are reported as they are.
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
from demand_forecasting import m5_data  # noqa: E402
from demand_forecasting.m5_track import (  # noqa: E402
    NAIVE,
    _lgbm_forecast,
    _statistical_forecasts,
    ensemble_weight,
    ensemble_weights,
    naive28_scale,
    paired_bootstrap_wape,
    pinball_loss,
    rmae,
    run_m5_track,
    wape,
    wrmsse_units,
)

N_DAYS = 150


def _tiny_frames(n_series: int = 3, n_days: int = N_DAYS, seed: int = 0):
    """Deterministic tiny M5-like frames: weekly demand + price + events."""
    rng = np.random.default_rng(seed)
    ids = [f"ITEM_{i:02d}_CA_3" for i in range(n_series)]
    days = pd.date_range("2020-01-01", periods=n_days, freq="D")
    recs, xrecs = [], []
    for sid in ids:
        base = 5.0 + 3.0 * (int(sid[5:7]) % 3)
        weekly = 2.0 * np.sin(np.arange(n_days) * 2 * np.pi / 7)
        trend = np.arange(n_days) * 0.01
        y = np.maximum(rng.poisson(base, n_days).astype(float) + weekly + trend, 0.0)
        if sid.endswith("02_CA_3"):
            # one genuinely intermittent series: demand on ~20% of days
            y = np.where(rng.random(n_days) < 0.2, y * 4.0, 0.0)
        price = np.round(1.5 + 0.1 * (int(sid[5:7]) % 4), 2)
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
        {
            "unique_id": ids,
            "item_id": [f"ITEM_{i:02d}" for i in range(n_series)],
            "dept_id": ["FOODS_1"] * n_series,
            "cat_id": ["FOODS"] * n_series,
            "store_id": ["CA_3"] * n_series,
            "state_id": ["CA"] * n_series,
        }
    )
    return ydf, xdf, sdf


def _write_tiny_m5(
    tmp_path: Path, ydf: pd.DataFrame, xdf: pd.DataFrame, sdf: pd.DataFrame
) -> tuple[Path, dict[str, str]]:
    """Write tiny frames as the subset parquets and pin their checksums."""
    data_dir = tmp_path / "data_m5"
    data_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, frame in (("subset_Y", ydf), ("subset_X", xdf), ("subset_S", sdf)):
        path = data_dir / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        checksums[f"{name}.parquet"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return data_dir, checksums


@pytest.fixture
def tiny_m5_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tiny on-disk M5 subset with patched checksum pins."""
    data_dir, checksums = _write_tiny_m5(tmp_path, *_tiny_frames())
    monkeypatch.setattr(m5_data, "M5_CHECKSUMS", checksums)
    return data_dir


def _track_kwargs():
    return dict(n_origins=4, n_test_origins=2, min_train=60, bootstrap_reps=200, n_estimators=25)


# ---------------------------------------------------------------------------
# Pure helpers: hand-computed cases
# ---------------------------------------------------------------------------


def test_rolling_origins_plan():
    dates = np.arange("2021-01-01", 200, dtype="datetime64[D]")
    origins = m5_data.rolling_origins(dates, n_origins=3, horizon=28, min_train=100, spacing_days=7)
    # eligible: first=99, last=171, step 7 -> last three are 155, 162, 169
    assert origins == [155, 162, 169]
    with pytest.raises(ValueError, match="too short"):
        m5_data.rolling_origins(dates[:80], n_origins=3, horizon=28, min_train=100)


def test_naive28_scale_hand_value():
    y = np.arange(29, dtype=float)  # y[t] - y[t-28] == 28 exactly
    assert naive28_scale(y) == pytest.approx(28.0**2)
    assert np.isnan(naive28_scale(np.arange(10, dtype=float)))


def test_wrmsse_hand_value():
    # unit 0: errors [3, 4] -> MSE 12.5, scale 6.25 -> RMSSE sqrt(2)
    # unit 1: errors [0, 0] -> RMSSE 0. volumes 1 and 3.
    err = np.array([[3.0, 4.0], [0.0, 0.0]])
    scales = np.array([6.25, 4.0])
    vols = np.array([1.0, 3.0])
    pooled, weighted = wrmsse_units(err, scales, vols)
    assert pooled == pytest.approx(np.sqrt(2.0) / 2)
    assert weighted == pytest.approx(np.sqrt(2.0) / 4)
    # zero/NaN-scale units are excluded, not infinite
    pooled2, _ = wrmsse_units(err, np.array([0.0, np.nan]), vols)
    assert np.isnan(pooled2)


def test_rmae_floor():
    assert rmae(5.0, 0.0) == 1.0
    assert rmae(5.0, 10.0) == 0.5


def test_wape_and_pinball():
    y = np.array([2.0, 4.0, 4.0, 4.0])
    assert wape(y, np.array([1.0, 5.0, 4.0, 4.0])) == pytest.approx(2.0 / 14.0)
    assert np.isnan(wape(np.zeros(3), np.zeros(3)))
    # pinball at tau=0.5 is MAE/2 for any forecast
    assert pinball_loss(y, np.zeros(4), 0.5) == pytest.approx(np.abs(y).mean() / 2)


def test_ensemble_weight_toy():
    y = np.array([10.0, 20.0, 30.0])
    a, b = y + 2.0, y - 2.0
    assert ensemble_weight(a, b, y) == 0.5  # |4w - 2| minimised at w=0.5
    assert ensemble_weight(y + 5.0, y, y) == 0.0  # b is perfect
    assert ensemble_weight(y, y + 5.0, y) == 1.0  # a is perfect


def test_ensemble_weights_simplex_toy():
    """The 0.05-step simplex grid picks the best convex combination."""
    y = np.array([10.0, 20.0, 30.0, 40.0])
    perfect = y.copy()
    a, c = y + 2.0, y + 4.0
    w = ensemble_weights([a, perfect, c], y)
    assert w.shape == (3,)
    assert w.sum() == pytest.approx(1.0)
    assert w[1] == 1.0  # all weight on the perfect member
    # a tie (identical members) resolves to the lexicographically first point
    w = ensemble_weights([a, a, c], y)
    assert list(w) == [0.0, 1.0, 0.0]
    # anti-correlated errors cancel at w2 = 0.5 (first lexicographic minimiser)
    p1, p2, p3 = y + 3.0, y - 3.0, y + 3.0
    w = ensemble_weights([p1, p2, p3], y)
    assert list(w) == [0.0, 0.5, 0.5]
    # brute-force consistency: the returned weights never lose to a grid point
    members = [y + 2.0, y - 2.0, y + 6.0]
    w = ensemble_weights(members, y)
    err = lambda p: float(np.sum(np.abs(p - y)))  # noqa: E731
    combo = sum(wi * pi for wi, pi in zip(w, members, strict=True))
    for g1 in np.arange(0, 1.0001, 0.05):
        for g2 in np.arange(0, 1.0001 - g1, 0.05):
            cand = g1 * members[0] + g2 * members[1] + (1 - g1 - g2) * members[2]
            assert err(combo) <= err(cand) + 1e-9


def test_bootstrap_pairs_on_shared_draws():
    y = np.ones(4)
    a = y + np.array([0.1, 0.1, 0.1, 0.1])
    b = y + np.array([0.3, 0.3, 0.3, 0.3])
    ser = np.array([0, 0, 1, 1])
    out = paired_bootstrap_wape(np.abs(a - y), np.abs(b - y), y, ser, n_boot=100, seed=7)
    # per-series demand is 2 and 2, so the WAPE gap equals the MAE gap: 0.1 - 0.3
    assert out["diff"] == pytest.approx(0.1 - 0.3)
    assert out["ci95"][1] < 0.0  # a is uniformly better; CI must exclude 0


# ---------------------------------------------------------------------------
# Loader + candidate alignment
# ---------------------------------------------------------------------------


def test_loader_checksum_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir, checksums = _write_tiny_m5(tmp_path, *_tiny_frames())
    monkeypatch.setattr(m5_data, "M5_CHECKSUMS", checksums)
    y, _x, s = m5_data.load_m5_subset(data_dir)
    assert len(s) == 3 and len(y) == 3 * N_DAYS
    # drift one file: rewrite Y with different content -> loud failure
    y2 = y.copy()
    y2.loc[0, "y"] = 999.0
    y2.to_parquet(data_dir / "subset_Y.parquet", index=False)
    with pytest.raises(ValueError, match="checksum"):
        m5_data.load_m5_subset(data_dir)


def test_seasonal_naive_alignment():
    """statsforecast SeasonalNaive must repeat the last observed week."""
    n_days, h = 70, 28
    ids = ["sA", "sB"]
    days = pd.date_range("2021-01-04", periods=n_days, freq="D")  # Monday start
    vals = {
        "sA": (10 + np.arange(n_days) % 7).astype(float),
        "sB": (100 + (np.arange(n_days) * 3) % 7).astype(float),
    }
    df = pd.DataFrame(
        {
            "unique_id": np.repeat(ids, n_days),
            "ds": np.tile(days, 2),
            "y": np.concatenate([vals["sA"], vals["sB"]]),
        }
    )
    train = df[df["ds"] <= days[55]]  # origin at day 55
    preds = _statistical_forecasts(train, ids, h)
    sn = preds[NAIVE]
    assert sn.shape == (2, h)
    last_week = {sid: vals[sid][49:56] for sid in ids}  # days 49..55
    for i, sid in enumerate(ids):
        for k in range(h):
            assert sn[i, k] == last_week[sid][(k) % 7]


def test_lgbm_determinism_toy(tiny_m5_dir: Path):
    y, x, s = m5_data.load_m5_subset(tiny_m5_dir)
    ids = sorted(y["unique_id"].unique().tolist())
    state_of = s.drop_duplicates("unique_id").set_index("unique_id")["state_id"]
    x_enc = m5_data.encode_events(x, x["unique_id"].map(state_of))
    odate = y["ds"].max() - pd.to_timedelta(28, unit="D")
    train = y[y["ds"] <= odate]
    hist_exog, future_exog = m5_data.split_exogenous(x_enc, ids, odate, 28)
    p1 = _lgbm_forecast(train, hist_exog, future_exog, seed=42, n_estimators=25, series_ids=ids)
    p2 = _lgbm_forecast(train, hist_exog, future_exog, seed=42, n_estimators=25, series_ids=ids)
    assert p1.shape == (3, 28)
    assert p1.tobytes() == p2.tobytes()
    # rows follow the caller's series_ids order, not mlforecast's alphabetical default
    rev = _lgbm_forecast(
        train, hist_exog, future_exog, seed=42, n_estimators=25, series_ids=list(reversed(ids))
    )
    assert np.array_equal(rev, p1[::-1])


# ---------------------------------------------------------------------------
# Full-track tiny run: byte-identity across runs
# ---------------------------------------------------------------------------


def _dump(result) -> str:
    return json.dumps(
        {"m": result.metrics, "p": result.probabilistic}, sort_keys=True, allow_nan=False
    )


def test_tiny_track_run_twice_byte_identical(tiny_m5_dir: Path):
    r1 = run_m5_track(tiny_m5_dir, **_track_kwargs())
    r2 = run_m5_track(tiny_m5_dir, **_track_kwargs())
    assert _dump(r1) == _dump(r2)
    # structural invariants on the tiny run
    assert r1.metrics["protocol"] == "m5_direct_v1"
    assert r1.metrics["origins"]["test"] == r1.metrics["origins"]["dates"][-2:]
    pooled = r1.metrics["test"]["pooled"]
    for cand in ("seasonal_naive", "lgbm", "convex_ensemble"):
        for key in ("mae", "wape", "rmae", "wrmsse", "peak_mae"):
            assert key in pooled[cand]
    assert pooled["lgbm"]["rmae"] >= 0.0
    assert set(r1.probabilistic["candidates"]) == {"lgbm", "convex_ensemble"}


# ---------------------------------------------------------------------------
# Real-subset smoke (committed data, deterministic 20-series subset)
# ---------------------------------------------------------------------------

REAL_M5 = Path(__file__).resolve().parent.parent / "data_m5"


@pytest.mark.skipif(not REAL_M5.exists(), reason="committed M5 subset not present")
def test_real_subset_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    y, x, s = m5_data.load_m5_subset(REAL_M5)
    keep = sorted(y["unique_id"].unique().tolist())[:20]
    data_dir, checksums = _write_tiny_m5(
        tmp_path,
        y[y["unique_id"].isin(keep)],
        x[x["unique_id"].isin(keep)],
        s[s["unique_id"].isin(keep)],
    )
    monkeypatch.setattr(m5_data, "M5_CHECKSUMS", checksums)
    kwargs = dict(n_origins=2, n_test_origins=1, min_train=1500, bootstrap_reps=200)
    r1 = run_m5_track(data_dir, **kwargs)
    r2 = run_m5_track(data_dir, **kwargs)
    assert _dump(r1) == _dump(r2)  # determinism on real data

    pooled = r1.metrics["test"]["pooled"]
    assert len(r1.metrics["origins"]["test"]) == 1
    for cand in r1.metrics["candidates"]:
        w = pooled[cand]["wape"]
        assert w == w and w > 0, f"{cand}: WAPE must be a positive finite number"
        assert pooled[cand]["mae"] >= 0
    assert (
        r1.metrics["classes"]["counts"]["dense"] + r1.metrics["classes"]["counts"]["intermittent"]
        == 20
    )
    # honest report of the total-level comparison (win NOT asserted)
    lgbm_wape, naive_wape = pooled["lgbm"]["wape"], pooled[NAIVE]["wape"]
    if lgbm_wape < naive_wape:
        print(f"\nSMOKE: lgbm beats naive on total WAPE ({lgbm_wape:.4f} < {naive_wape:.4f})")
    else:
        print(f"\nSMOKE (honest): lgbm does NOT beat naive ({lgbm_wape:.4f} >= {naive_wape:.4f})")
