"""Pass-4 E9 refit driver: toy end-to-end + committed-artifact contracts.

The toy fixture runs the tiny full track (20 series, direct pooled) with a
FORCED 0.95/0.00/0.05 committed ensemble (so the driver's active-member
contract holds), dumps the wave-32 catalog against it, then runs the E9
refit: the reproduction gate must pass with ~0 deltas, the catalog must move
onto the committed blend, and the interval/metadata artifacts must appear.
Also covers the gate's abort path (tampered committed score -> no write),
the seeded node-bootstrap idiom, and — against the REAL committed artifacts —
the restored sample-series figure, the headline interval, and the metadata
log.
"""

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
TESTS = Path(__file__).resolve().parent
for p in (str(SRC), str(TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from demand_forecasting import m5_full  # noqa: E402
from demand_forecasting.evaluate import _json_safe  # noqa: E402
from demand_forecasting.m5_full import CANDIDATES, PROTOCOL, run_m5_full  # noqa: E402
from demand_forecasting.m5_full_refit import (  # noqa: E402
    HEADLINE_BOOT_SEED_OFFSET,
    HEADLINE_INTERVAL_NAME,
    METADATA_BLOCK,
    REFIT_MEMBERS,
    RefitReproductionError,
    node_bootstrap_ci,
    run_m5_full_refit,
)
from demand_forecasting.m5_track import SEED  # noqa: E402
from test_m5_full import _track_frames, _write_tiny_full  # noqa: E402  (shared toy builders)

REPORTS = Path(__file__).resolve().parent.parent / "reports_m5_full"


def _forced_ensemble(forecasts, selection, origin_ctx, **kwargs):
    """Stand-in for the wave-30 screen: pin the committed 0.95/0.00/0.05 blend
    (same members/weights as the real committed run) so the toy metrics carry
    the true score of THAT blend — exactly what the refit gate must reproduce."""
    members = ["lgbm_pool_storecat", "lgbm_pool_store", "lgbm_pool_dept"]
    weights = np.array([0.95, 0.0, 0.05])
    for o in forecasts[members[0]]:
        combo = np.zeros_like(forecasts[members[0]][o])
        for wi, member in zip(weights, members, strict=True):
            combo += wi * forecasts[member][o]
        forecasts["convex_ensemble"][o] = combo
    screen = {
        c: {"mean": 0.0, "std": 0.0, "score": 0.0} for c in CANDIDATES if c != "convex_ensemble"
    }
    return members, weights, screen


@pytest.fixture(scope="module")
def e9_toy_artifacts(tmp_path_factory: pytest.TempPathFactory):
    """Tiny direct full track with the forced committed ensemble + catalog dump."""
    from demand_forecasting.m5_full_catalog import run_m5_full_catalog

    tmp = tmp_path_factory.mktemp("m5full_e9_toy")
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp, y, x, s)
    mp = pytest.MonkeyPatch()
    mp.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    mp.setattr(m5_full, "screened_ensemble", _forced_ensemble)
    try:
        track_kwargs = dict(min_train=140, n_estimators=5, params_path=tmp / "no_params.yaml")
        committed = run_m5_full(raw, n_origins=2, pooled_strategy="direct", **track_kwargs)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "metrics.json").write_text(json.dumps(_json_safe(committed.metrics)))
        (reports / "evaluation_metadata.json").write_text(
            json.dumps(_json_safe(committed.metadata))
        )
        run_m5_full_catalog(
            raw,
            reports / "catalog_forecasts.parquet",
            metrics_path=reports / "metrics.json",
            catalog_size=12,
            series_cap=None,
            pooled_strategy="recursive",
            **track_kwargs,
        )
        yield raw, reports, tmp / "cache", tmp / "no_params.yaml"
    finally:
        mp.undo()


# ---------------------------------------------------------------------------
# node_bootstrap_ci (pure)
# ---------------------------------------------------------------------------


def test_node_bootstrap_ci_seeded_and_consistent() -> None:
    rng = np.random.default_rng(7)
    rmsse = rng.gamma(2.0, 0.4, size=500)
    w = rng.random(500) + 0.01
    out = node_bootstrap_ci(rmsse, w, n_boot=500, seed=123)
    again = node_bootstrap_ci(rmsse, w, n_boot=500, seed=123)
    assert out == again  # seeded: identical draws
    assert out["point"] == pytest.approx(float((w * rmsse).sum() / w.sum()))
    lo, hi = out["ci95"]
    assert lo <= out["point"] <= hi
    assert out["n_boot"] == 500 and out["seed"] == 123
    other = node_bootstrap_ci(rmsse, w, n_boot=500, seed=124)
    assert other["ci95"] != out["ci95"]  # a different seed moves the draws


# ---------------------------------------------------------------------------
# Toy end-to-end: gate passes, artifacts repaired
# ---------------------------------------------------------------------------


def test_refit_reproduces_committed_and_repairs_catalog(e9_toy_artifacts):
    raw, reports, cache, params = e9_toy_artifacts
    before = pd.read_parquet(reports / "catalog_forecasts.parquet")
    result = run_m5_full_refit(
        raw,
        reports,
        n_workers=2,
        n_boot=200,
        cache_dir=cache,
        n_origins=2,
        min_train=140,
        n_estimators=5,
        params_path=params,
    )

    repro = result["reproduction"]
    assert repro["passed"] is True
    for name in (*REFIT_MEMBERS, "convex_ensemble"):
        assert repro["members"][name]["abs_delta"] < 1e-9  # same code path: ~exact
    interval = result["headline_interval"]
    # the bootstrap point recomputes the weighted mean over the compacted
    # valid-node vectors — same estimand as the gate's official_wrmsse, with
    # a ~1e-8 pairwise-summation-order difference, well inside the 1e-6 gate
    assert interval["point"] == pytest.approx(
        repro["members"]["convex_ensemble"]["refit"], abs=1e-6
    )
    lo, hi = interval["ci95"]
    assert lo <= interval["point"] <= hi
    assert interval["seed"] == SEED + HEADLINE_BOOT_SEED_OFFSET

    after = pd.read_parquet(reports / "catalog_forecasts.parquet")
    committed = json.loads((reports / "metrics.json").read_text())
    members = committed["ensemble"]["members"]
    weights = committed["ensemble"]["weights"]
    blend = np.zeros(len(after))
    for w, m in zip(weights, members, strict=True):
        blend += w * after[m].to_numpy(dtype=float)
    np.testing.assert_allclose(blend, after["convex_ensemble"].to_numpy(dtype=float), atol=1e-9)
    # the zero-weight member column carried over untouched
    assert np.array_equal(before["lgbm_pool_store"].to_numpy(), after["lgbm_pool_store"].to_numpy())
    # the refit members moved to the direct fits (the toy catalog was recursive)
    assert not np.array_equal(
        before["lgbm_pool_storecat"].to_numpy(), after["lgbm_pool_storecat"].to_numpy()
    )
    band = np.stack([after[m].to_numpy(dtype=float) for m in members])
    np.testing.assert_allclose(after["band_lo"], band.min(axis=0))
    np.testing.assert_allclose(after["band_hi"], band.max(axis=0))

    interval_json = json.loads((reports / HEADLINE_INTERVAL_NAME).read_text())
    assert interval_json["seed"] == SEED + HEADLINE_BOOT_SEED_OFFSET
    assert interval_json["n_boot"] == 200
    meta = json.loads((reports / "evaluation_metadata.json").read_text())
    assert meta[METADATA_BLOCK]["reproduction"]["passed"] is True
    cat_meta = json.loads((reports / "catalog_meta.json").read_text())
    assert cat_meta["ensemble"]["weights"] == weights
    assert METADATA_BLOCK in cat_meta


def test_refit_gate_aborts_without_writes(e9_toy_artifacts):
    raw, reports, cache, params = e9_toy_artifacts
    metrics_path = reports / "metrics.json"
    committed = json.loads(metrics_path.read_text())
    tampered = json.loads(metrics_path.read_text())
    tampered["test"]["lgbm_pool_storecat"]["official_wrmsse"] += 1e-3
    metrics_path.write_text(json.dumps(tampered))
    parquet_bytes = (reports / "catalog_forecasts.parquet").read_bytes()
    interval_bytes = (reports / HEADLINE_INTERVAL_NAME).read_bytes()
    try:
        with pytest.raises(RefitReproductionError, match="reproduction gate"):
            run_m5_full_refit(
                raw,
                reports,
                n_workers=2,
                n_boot=50,
                cache_dir=cache,
                n_origins=2,
                min_train=140,
                n_estimators=5,
                params_path=params,
            )
        assert (reports / "catalog_forecasts.parquet").read_bytes() == parquet_bytes
        assert (reports / HEADLINE_INTERVAL_NAME).read_bytes() == interval_bytes
    finally:
        metrics_path.write_text(json.dumps(committed))


# ---------------------------------------------------------------------------
# Committed artifacts (the real reports_m5_full): figure, interval, metadata
# ---------------------------------------------------------------------------


def test_committed_headline_interval_structure() -> None:
    interval = json.loads((REPORTS / HEADLINE_INTERVAL_NAME).read_text())
    metrics = json.loads((REPORTS / "metrics.json").read_text())
    assert interval["protocol"] == PROTOCOL
    assert interval["candidate"] == "convex_ensemble"
    assert interval["metric"] == "official_wrmsse"
    assert interval["point"] == pytest.approx(
        metrics["test"]["convex_ensemble"]["official_wrmsse"], abs=1e-6
    )
    lo, hi = interval["ci95"]
    assert lo <= interval["point"] <= hi
    assert interval["n_boot"] == 2000
    assert interval["seed"] == SEED + HEADLINE_BOOT_SEED_OFFSET
    # zero-revenue nodes drop out of the resampling frame, exactly like the
    # committed erratic-refinement bootstrap (same idiom, same valid set)
    erratic = metrics["erratic_refinement"]["wrmsse_delta_bootstrap_routed_vs_champion"]
    assert interval["n_valid_nodes"] == erratic["n_valid_nodes"]
    assert "node bootstrap" in interval["method"]


def test_committed_metadata_logs_e9_reproduction() -> None:
    meta = json.loads((REPORTS / "evaluation_metadata.json").read_text())
    block = meta[METADATA_BLOCK]
    assert block["reproduction"]["passed"] is True
    assert block["reproduction"]["tolerance"] == 1e-6
    assert set(block["members_refit"]) == set(REFIT_MEMBERS)
    for name, entry in block["reproduction"]["members"].items():
        assert entry["abs_delta"] <= 1e-6, name


def test_sample_series_figure_reproduces_from_committed_artifacts() -> None:
    """The restored figure builder, run on the committed artifacts, matches the
    committed figure JSON (title, takeaway, traces, per-series blend curves)."""
    from demand_forecasting.m5_full_figures import SAMPLE_SERIES, fig_sample_series

    frame = pd.read_parquet(REPORTS / "catalog_forecasts.parquet")
    cat_meta = json.loads((REPORTS / "catalog_meta.json").read_text())
    payload = json.loads((REPORTS / "demo_payload.json").read_text())
    committed_fig = json.loads((REPORTS / "figures" / "m5_full_sample_series.json").read_text())

    fig = fig_sample_series(frame, cat_meta, payload)
    rebuilt = json.loads(fig.to_json())
    assert rebuilt["layout"]["title"] == committed_fig["layout"]["title"]
    title_text = rebuilt["layout"]["title"]["text"]
    assert "0.6211" in title_text
    assert "0.95" in title_text and "0.05" in title_text
    assert "earlier" not in title_text
    assert len(rebuilt["data"]) == len(committed_fig["data"])
    # per-series blend curves in the figure equal the committed parquet values
    history_of = {e["series_id"]: e["windows"]["history"] for e in payload["catalog"]}
    traces = rebuilt["data"]
    for i, (sid, _label) in enumerate(SAMPLE_SERIES):
        row = frame[frame["unique_id"] == sid].sort_values("ds")
        blend_trace = traces[i * 5 + 2]  # history, actual, blend, band lo, band hi
        assert blend_trace["name"] == "convex_ensemble"
        np.testing.assert_allclose(
            blend_trace["y"], row["convex_ensemble"].to_numpy(dtype=float), atol=1e-9
        )
        hist_trace = traces[i * 5]
        np.testing.assert_allclose(hist_trace["y"], history_of[sid], atol=1e-9)
