"""Tests for the forecast-workbench M5 demo payload (schema version 4).

The suite runs on the same tiny on-disk M5 subset as test_m5.py (3 series x
150 days, monkeypatched checksum pins): the track runs once with the fast
kwargs, its artifacts land in a tmp reports dir, and the payload is built
against them — so the drift guard, catalog quotas and shape checks all
exercise the real code paths without the 22-minute evaluate.
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
from demand_forecasting.m5_demo_payload import (  # noqa: E402
    CATALOG_PER_CELL,
    CURVE_CANDIDATES,
    HISTORY_DAYS,
    SCHEMA_VERSION,
    _select_catalog,
    _shape_tag,
    build_demo_payload,
    write_demo_payload,
)
from demand_forecasting.m5_track import run_m5_track, write_m5_artifacts  # noqa: E402

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
    data_dir = tmp_path / "data_m5"
    data_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, frame in (("subset_Y", ydf), ("subset_X", xdf), ("subset_S", sdf)):
        path = data_dir / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        checksums[f"{name}.parquet"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return data_dir, checksums


@pytest.fixture
def tiny_m5_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tiny on-disk M5 subset + a real (fast) track run + the built payload."""
    data_dir, checksums = _write_tiny_m5(tmp_path, *_tiny_frames())
    monkeypatch.setattr(m5_data, "M5_CHECKSUMS", checksums)
    result = run_m5_track(
        data_dir, n_origins=4, n_test_origins=2, min_train=60, bootstrap_reps=200, n_estimators=25
    )
    reports_dir = tmp_path / "reports_m5"
    write_m5_artifacts(result, reports_dir)
    payload = build_demo_payload(data_dir, reports_dir, per_cell=2)
    return data_dir, reports_dir, payload


# ---------------------------------------------------------------------------
# Hand-shape checks
# ---------------------------------------------------------------------------


def test_payload_top_level_contract(tiny_m5_payload) -> None:
    _, _, payload = tiny_m5_payload
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["demo"] == "forecast-workbench"
    assert payload["project"] == "02-demand-forecasting"
    assert payload["protocol"] == "m5_direct_v1"
    for key in ("demo", "project", "protocol", "catalog", "groups", "evaluation_metadata"):
        assert key in payload, f"required key {key!r} missing"
    # the committed headline block is present verbatim
    groups = payload["groups"]
    keys = ("headline", "test_pooled", "test_by_class", "win_rate_vs_naive", "band", "ensemble")
    for key in keys:
        assert key in groups, f"groups block missing {key!r}"
    assert set(groups["test_pooled"]) >= set(CURVE_CANDIDATES)
    assert "coverage_80" in groups["band"]["candidates"]["lgbm"]


def test_catalog_window_shapes(tiny_m5_payload) -> None:
    _, reports_dir, payload = tiny_m5_payload
    metrics = json.loads((reports_dir / "metrics.json").read_text())
    test_dates = set(metrics["origins"]["test"])
    assert {b["origin"] for b in payload["origins"]} == test_dates
    assert payload["catalog"], "catalog empty"
    for entry in payload["catalog"]:
        assert entry["store"] == "CA_3"  # tiny panel is single-store
        assert entry["class"] in ("dense", "intermittent")
        assert set(entry["origins"]) == set(test_dates)
        for win in entry["origins"].values():
            assert len(win["history"]) == HISTORY_DAYS
            assert len(win["actual"]) == 28
            assert set(CURVE_CANDIDATES) <= set(win["curves"])
            for curve in win["curves"].values():
                assert len(curve) == 28
                assert all(isinstance(v, float) for v in curve)
            assert len(win["band"]["p10"]) == 28 and len(win["band"]["p90"]) == 28
            # zero-clipped, sorted band around the lgbm curve
            p50 = win["curves"]["lgbm"]
            for lo, hi, p in zip(win["band"]["p10"], win["band"]["p90"], p50, strict=True):
                assert 0.0 <= lo <= hi
                assert hi >= p >= lo - 1e-3  # 4-decimal rounding
            assert set(CURVE_CANDIDATES) <= set(win["wape"])
            assert win["shape"] in ("steady", "weekly-peaked", "event-driven", "slow-mover")


def test_ensemble_curve_uses_committed_rule(tiny_m5_payload) -> None:
    _, _, payload = tiny_m5_payload
    ens = payload["groups"]["ensemble"]
    a, b = ens["members"]
    w = ens["weight_on_a"]
    for entry in payload["catalog"]:
        for win in entry["origins"].values():
            blend = zip(win["curves"][a], win["curves"][b], strict=True)
            expected = [w * x + (1 - w) * y for x, y in blend]
            assert win["curves"]["convex_ensemble"] == pytest.approx(expected, abs=2e-4)


def test_wape_entries_match_hand_computation(tiny_m5_payload) -> None:
    """Per-series WAPE in the payload is Σ|err|/Σy of the committed curves."""
    _, _, payload = tiny_m5_payload
    for entry in payload["catalog"]:
        for win in entry["origins"].values():
            actual = np.asarray(win["actual"], dtype=float)
            for cand in CURVE_CANDIDATES:
                curve = np.asarray(win["curves"][cand], dtype=float)
                expected = float(np.sum(np.abs(curve - actual)) / np.sum(actual))
                assert win["wape"][cand] == pytest.approx(expected, abs=2e-4)


# ---------------------------------------------------------------------------
# Catalog selection: quotas, determinism, shapes
# ---------------------------------------------------------------------------


def test_select_catalog_balance_quotas() -> None:
    """Synthetic multi-store class table: per-cell picks are balanced and
    volume-diverse (high/mid/low ranks)."""
    ids = [f"ITEM_{s}_{i:02d}" for s in ("CA_1", "TX_2") for i in range(6)]
    rows = []
    for i, sid in enumerate(ids):
        rows.append((sid, 10.0 * (i + 1)))
    y = pd.DataFrame(rows, columns=["unique_id", "y"])
    y = y.loc[y.index.repeat(3)].reset_index(drop=True)  # volume = 3x the id factor
    y["ds"] = pd.date_range("2020-01-01", periods=len(y), freq="D")
    classes = {
        sid: {"class": "intermittent" if i % 3 == 2 else "smooth"} for i, sid in enumerate(ids)
    }
    stores = pd.Series(
        ["CA_1" if sid.startswith("ITEM_CA_1") else "TX_2" for sid in ids], index=ids
    )
    picked = _select_catalog(y, classes, stores, per_cell=2)
    # 2 stores x (2 dense + 2 intermittent): dense cell -> ranks [0, 1],
    # intermittent cell (2 members) -> ranks [0, 1]
    assert len(picked) == 2 * (2 + 2)
    by_store = {}
    for sid in picked:
        by_store.setdefault(stores.loc[sid], []).append(sid)
    assert set(by_store) == {"CA_1", "TX_2"}
    for _store, members in by_store.items():
        dense = [s for s in members if classes[s]["class"] != "intermittent"]
        inter = [s for s in members if classes[s]["class"] == "intermittent"]
        assert len(dense) == 2 and len(inter) == 2
    # deterministic: same inputs -> same order
    assert picked == _select_catalog(y, classes, stores, per_cell=2)


def test_shape_tag_hand_cases():
    days = np.array([str(d.date()) for d in pd.date_range("2021-03-01", periods=56, freq="D")])
    no_events = np.zeros(56, dtype=bool)
    # weekly-peaked: unit demand on Sundays only (peak/mean = 7)
    weekly = np.where(pd.to_datetime(days).dayofweek == 6, 7.0, 0.0)
    assert _shape_tag(weekly, days, no_events, "erratic") == "weekly-peaked"
    # slow-mover: intermittent class with a sparse tail (>=25% zero days)
    sparse = np.zeros(56)
    sparse[::3] = 5.0
    assert _shape_tag(sparse, days, no_events, "intermittent") == "slow-mover"
    # steady: flat dense demand, no events
    flat = np.full(56, 4.0)
    assert _shape_tag(flat, days, no_events, "smooth") == "steady"
    # event-driven: >=20% of demand on event days, spread across four weekdays
    # so no single weekday peaks above the 1.5x weekly threshold
    dow = pd.to_datetime(days).dayofweek.to_numpy()
    events = np.isin(dow, [0, 1, 3, 4])
    with_events = np.full(56, 4.0)
    with_events[events] = 10.0  # 320/416 ≈ 77% of demand on event days
    assert _shape_tag(with_events, days, events, "smooth") == "event-driven"


# ---------------------------------------------------------------------------
# Drift guard + byte identity
# ---------------------------------------------------------------------------


def test_drift_guard_raises_on_tampered_metrics(tiny_m5_payload) -> None:
    data_dir, reports_dir, _ = tiny_m5_payload
    metrics_path = reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    metrics["test"]["pooled"]["seasonal_naive"]["wape"] += 0.5
    metrics_path.write_text(json.dumps(metrics))
    with pytest.raises(ValueError, match="drift guard failed"):
        build_demo_payload(data_dir, reports_dir, per_cell=2)


def test_run_twice_byte_identity(tiny_m5_payload) -> None:
    data_dir, reports_dir, payload = tiny_m5_payload
    again = build_demo_payload(data_dir, reports_dir, per_cell=2)
    assert json.dumps(payload, indent=2) + "\n" == json.dumps(again, indent=2) + "\n"


def test_write_demo_payload_is_byte_identical(tiny_m5_payload) -> None:
    data_dir, reports_dir, _ = tiny_m5_payload
    first = write_demo_payload(data_dir, reports_dir).read_bytes()
    second = write_demo_payload(data_dir, reports_dir).read_bytes()
    assert first == second
    payload = json.loads(first)
    assert payload["schema_version"] == SCHEMA_VERSION
    # the catalog quota constant is what the real build uses
    assert CATALOG_PER_CELL == 4
