"""M5 FULL-panel payload + report builders: toy end-to-end tests.

One module-scoped fixture runs the tiny full track (20 series, 2 origins,
recursive pooled) and the wave-32 catalog dump on tmp parquet fixtures with
monkeypatched checksum pins, so the payload and report builders exercise the
real committed-artifact shapes: metrics.json + evaluation_metadata.json +
catalog_forecasts.parquet + catalog_meta.json next to each other.

Covers: the schema keys the workbench reads (mirroring the subset payload),
the _scope honesty notes, win-rate-vs-naive correctness against a manual
recomputation, byte-determinism of the payload, the 1 MB cap, the report's
self-contained figures (tables-only when the catalog is absent), and the
no-drift guarantee on the committed metrics.
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
import pytest  # noqa: E402
from demand_forecasting import m5_full  # noqa: E402
from demand_forecasting.evaluate import _json_safe  # noqa: E402
from demand_forecasting.m5_full import CANDIDATES, PROTOCOL, run_m5_full  # noqa: E402
from test_m5_full import _track_frames, _write_tiny_full  # noqa: E402  (shared toy builders)

GROUP_KEYS = {
    "headline",
    "test_pooled",
    "test_by_class",
    "win_rate_vs_naive",
    "stability",
    "classes",
    "ensemble",
    "band",
    "_scope",
}


@pytest.fixture(scope="module")
def full_track_artifacts(tmp_path_factory: pytest.TempPathFactory):
    """Tiny full track + catalog dump -> (raw_dir, reports_dir)."""
    from demand_forecasting.m5_full_catalog import run_m5_full_catalog

    tmp = tmp_path_factory.mktemp("m5full_toy")
    y, x, s = _track_frames()
    raw, checksums = _write_tiny_full(tmp, y, x, s)
    mp = pytest.MonkeyPatch()
    mp.setattr(m5_full, "FULL_CHECKSUMS", checksums)
    try:
        track_kwargs = dict(min_train=140, n_estimators=5, params_path=tmp / "no_params.yaml")
        committed = run_m5_full(raw, n_origins=2, pooled_strategy="recursive", **track_kwargs)
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
        yield raw, reports
    finally:
        mp.undo()


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def test_payload_schema_and_scope(full_track_artifacts):
    from demand_forecasting.m5_full_payload import build_demo_payload_full

    raw, reports = full_track_artifacts
    payload = build_demo_payload_full(raw, reports)

    assert payload["schema_version"] == 4
    assert payload["demo"] == "forecast-workbench"
    assert payload["protocol"] == PROTOCOL
    assert set(payload["groups"]) == GROUP_KEYS
    # _scope marks the catalog-based vs panel-based fields honestly
    scope = payload["groups"]["_scope"]
    assert "catalog" in scope["win_rate_vs_naive"]
    assert "catalog" in scope["test_by_class"]
    assert "panel" in scope["test_pooled"]
    assert "panel" in scope["ensemble"]

    test_pooled = payload["groups"]["test_pooled"]
    assert set(test_pooled) == set(CANDIDATES)
    for block in test_pooled.values():
        assert set(block) >= {"wape", "wrmsse", "bias"}
        assert block["wrmsse"] > 0

    win_rate = payload["groups"]["win_rate_vs_naive"]
    assert set(win_rate) == set(CANDIDATES)
    for block in win_rate.values():
        assert 0.0 <= block["pooled"] <= 1.0
        assert block["dense"] is None or 0.0 <= block["dense"] <= 1.0
        assert block["intermittent"] is None or 0.0 <= block["intermittent"] <= 1.0

    # per-class WAPE present for both classes on this fixture (both populated)
    for cand in CANDIDATES:
        assert payload["groups"]["test_by_class"][cand]["dense"]["wape"] >= 0
        assert payload["groups"]["test_by_class"][cand]["intermittent"]["wape"] >= 0

    # stability rides every candidate; ensemble copied verbatim from metrics
    assert set(payload["groups"]["stability"]) == set(CANDIDATES)
    metrics = json.loads((reports / "metrics.json").read_text())
    assert payload["groups"]["ensemble"]["members"] == metrics["ensemble"]["members"]

    # headline block mirrors the committed numbers
    headline = payload["groups"]["headline"]
    assert headline["champion"] == "convex_ensemble" or headline["champion"] in CANDIDATES
    assert headline["champion_wrmsse"] == pytest.approx(
        metrics["test"][headline["champion"]]["official_wrmsse"]
    )
    assert headline["convex_ensemble_vs_naive"]["wrmsse"]["rel"] == pytest.approx(
        (
            metrics["test"]["convex_ensemble"]["official_wrmsse"]
            - metrics["test"]["seasonal_naive"]["official_wrmsse"]
        )
        / metrics["test"]["seasonal_naive"]["official_wrmsse"]
    )

    # catalog section: per-series windows with every curve + the envelope band
    catalog = payload["catalog"]
    assert len(catalog) == 12
    for entry in catalog:
        assert entry["series_id"]
        assert len(entry["windows"]["history"]) == 56
        assert len(entry["windows"]["actual"]) == 28
        assert set(entry["windows"]["curves"]) == set(CANDIDATES)
        assert len(entry["windows"]["band"]["lo"]) == 28
        assert set(entry["windows"]["wape"]) == set(CANDIDATES)
    assert len(payload["origins"]) == 1
    assert len(payload["origins"][0]["forecast_dates"]) == 28


def test_payload_win_rate_matches_manual(full_track_artifacts):
    """The catalog-based win rate must equal a manual recomputation from the
    parquet (per-series total absolute error vs the seasonal_naive floor)."""
    import numpy as np
    import pyarrow.parquet as pq
    from demand_forecasting.m5_full_payload import build_demo_payload_full

    raw, reports = full_track_artifacts
    payload = build_demo_payload_full(raw, reports)
    frame = pq.read_table(reports / "catalog_forecasts.parquet").to_pandas()
    catalog_ids = list(dict.fromkeys(frame["unique_id"].tolist()))
    grids = {
        c: frame.pivot(index="unique_id", columns="ds", values=c)
        .reindex(catalog_ids)
        .to_numpy(dtype=float)
        for c in ("actual", "seasonal_naive", "convex_ensemble")
    }
    naive_err = np.abs(grids["seasonal_naive"] - grids["actual"]).sum(axis=1)
    ens_err = np.abs(grids["convex_ensemble"] - grids["actual"]).sum(axis=1)
    expected = float((ens_err < naive_err).mean())
    assert payload["groups"]["win_rate_vs_naive"]["convex_ensemble"]["pooled"] == pytest.approx(
        expected
    )


def test_payload_deterministic_and_capped(full_track_artifacts):
    from demand_forecasting.m5_full_payload import write_demo_payload_full

    raw, reports = full_track_artifacts
    out1 = write_demo_payload_full(raw, reports)
    bytes1 = out1.read_bytes()
    out2 = write_demo_payload_full(raw, reports)
    assert out2.read_bytes() == bytes1  # byte-identical rebuild
    assert len(bytes1) / 1024 < 1024  # the 1 MB demo cap


def test_payload_guards_tampered_ensemble(full_track_artifacts):
    """A catalog whose ensemble deviates from the committed metrics fails the
    build loudly (mixing artifacts from different runs)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from demand_forecasting.m5_full_payload import build_demo_payload_full

    raw, reports = full_track_artifacts
    path = reports / "catalog_forecasts.parquet"
    table = pq.read_table(path)
    df = table.to_pandas()
    df["convex_ensemble"] = df["convex_ensemble"].to_numpy(dtype=float) + 1.0
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
    try:
        with pytest.raises(ValueError, match="blend"):
            build_demo_payload_full(raw, reports)
    finally:
        # restore the artifact for the other tests
        meta = json.loads((reports / "catalog_meta.json").read_text())
        members = meta["ensemble"]["members"]
        weights = [float(w) for w in meta["ensemble"]["weights"]]
        blend = np.zeros(len(df))
        for w, m in zip(weights, members, strict=True):
            blend += w * df[m].to_numpy(dtype=float)
        df["convex_ensemble"] = blend
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)


def test_payload_requires_catalog(full_track_artifacts):
    import shutil

    from demand_forecasting.m5_full_payload import build_demo_payload_full

    raw, reports = full_track_artifacts
    other = reports.parent / "reports_no_catalog"
    other.mkdir(exist_ok=True)
    for name in ("metrics.json", "evaluation_metadata.json"):
        shutil.copy(reports / name, other / name)
    with pytest.raises(FileNotFoundError, match="catalog"):
        build_demo_payload_full(raw, other)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def test_report_full_builds_self_contained(full_track_artifacts):
    from demand_forecasting.m5_full_report import build_report_full

    _raw, reports = full_track_artifacts
    metrics_before = (reports / "metrics.json").read_text(encoding="utf-8")
    out = build_report_full(reports)
    html = out.read_text(encoding="utf-8")

    # all 8 candidates named; headline table + per-level (12 levels) + screen
    for cand in CANDIDATES:
        assert cand in html
    for lvl in ("total", "state", "store", "cat", "dept", "item_store"):
        assert f"<td>{lvl}</td>" in html
    # the honest comparison box: competition axis, our gap, protocol limits
    assert "22.4%" in html
    assert "2 selection origins" in html
    assert "wave 32" in html
    assert "seasonal-naive floor" in html
    # self-contained interactive figures: 3 (bars, per-level, catalog curves)
    assert html.count('class="plotly-graph-div"') == 3
    assert html.count("cdn.plot.ly") == 1
    # never touches the committed numbers
    assert (reports / "metrics.json").read_text(encoding="utf-8") == metrics_before
    assert "<table>" in html


def test_report_full_tables_only_without_catalog(full_track_artifacts):
    import shutil

    from demand_forecasting.m5_full_report import build_report_full

    _raw, reports = full_track_artifacts
    other = reports.parent / "reports_tables_only"
    other.mkdir(exist_ok=True)
    for name in ("metrics.json", "evaluation_metadata.json"):
        shutil.copy(reports / name, other / name)
    out = build_report_full(other)
    html = out.read_text(encoding="utf-8")
    assert "Tables only" in html
    assert html.count('class="plotly-graph-div"') == 2  # metrics-only figures
    for cand in CANDIDATES:
        assert cand in html


def test_report_full_requires_metrics(full_track_artifacts):
    from demand_forecasting.m5_full_report import build_report_full

    _raw, reports = full_track_artifacts
    with pytest.raises(FileNotFoundError):
        build_report_full(reports.parent / "no_such_dir")
