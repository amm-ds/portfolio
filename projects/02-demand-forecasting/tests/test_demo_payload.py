"""Demo payload contract: schema v3 — the direct multi-horizon catalog.

The fixture runs the REAL multi-step track (``run_multistep``) on a tiny
erratic+lumpy panel and writes the committed-metrics shape, so the builder's
drift guards, routing-table consistency and scoreboard numbers are exercised
against a genuine committed block — exactly the UCI regeneration path.
"""

import itertools
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.demo_payload import (
    PAYLOAD_SCHEMA_VERSION,
    SHOCK_FACTORS,
    SIZE_CAP_BYTES,
    build_demo_payload,
    write_demo_payload,
)
from demand_forecasting.intermittent import statistical_forecast
from demand_forecasting.multihorizon import (
    multistep_origin_indices,
    panel_matrix,
    run_multistep,
    split_origins,
)

# 12 weekly origins (4 scored test origins) — enough for the 3 scored origins
# the catalog needs; tiny bootstrap for speed. The full h = 1..14 lattice
# (revision 3.2): every window day is a real direct-h model.
MS_CONFIG = ForecastConfig(
    n_days=170,
    min_train_size=60,
    multistep_horizons=list(range(1, 15)),
    multistep_n_origins=12,
    multistep_test_origins=4,
    bootstrap_reps=200,
)
CATALOG_ARGS = {"catalog_n": 6, "origin_history_days": 45}
HORIZONS = MS_CONFIG.multistep_horizons


def _panel() -> pl.DataFrame:
    """8 series: 2 erratic (frequent, high-variance), 6 lumpy (rare bursts)."""
    dates = np.arange(
        np.datetime64("2024-01-01"), np.datetime64("2024-06-18"), dtype="datetime64[D]"
    )
    n = len(dates)
    rng = np.random.default_rng(11)

    def erratic() -> np.ndarray:
        return np.where(rng.random(n) < 0.85, np.round(rng.lognormal(1.5, 1.2, n)), 0)

    def lumpy() -> np.ndarray:
        return np.where(rng.random(n) < 0.25, np.round(rng.lognormal(2.0, 1.1, n)), 0)

    frames = []
    kinds = [erratic, erratic, lumpy, lumpy, lumpy, lumpy, lumpy, lumpy]
    for i, make in enumerate(kinds):
        store, product = ("UK", "EIRE")[i % 2], f"p{i}"
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": store,
                    "product": product,
                    "units": make().astype(int),
                }
            )
        )
    return pl.concat(frames)


def _write_committed(reports: Path, result) -> None:
    """The committed-metrics shape the v3 builder reads."""
    (reports / "metrics.json").write_text(json.dumps({"_multistep": result.block}))
    (reports / "probabilistic.json").write_text(
        json.dumps({"multistep": result.probabilistic_block})
    )
    (reports / "evaluation_metadata.json").write_text(
        json.dumps({"multi_horizon": result.metadata_block})
    )
    dataset = {
        "dataset": "fixture-panel",
        "source": {"url": "https://example.test/panel.zip", "sha256": "0" * 64},
        "observed_panel": {"date_start": "2024-01-01", "date_end": "2024-06-17"},
        "zero_sales_caveat": "Zero-sales days may be missing rather than true zero demand.",
        "target_definition": "The forecast target is the next 14 days of daily units per series.",
    }
    (reports / "dataset_metadata.json").write_text(json.dumps(dataset))


@pytest.fixture
def demo_context(tmp_path: Path) -> tuple[DemandSettings, ForecastConfig, pl.DataFrame]:
    """Tiny panel + its genuinely committed multi-step metrics."""
    settings = DemandSettings(
        data_dir=tmp_path / "data", reports_dir=tmp_path / "reports", min_newest_date="2023-01-01"
    )
    settings.data_dir.mkdir(parents=True)
    settings.reports_dir.mkdir(parents=True)
    panel = _panel()
    panel.write_parquet(settings.data_dir / "panel.parquet")
    result = run_multistep(settings=settings, config=MS_CONFIG, panel=panel)
    _write_committed(settings.reports_dir, result)
    return settings, MS_CONFIG, panel


@pytest.fixture
def payload(demo_context) -> dict:
    settings, config, _panel = demo_context
    return build_demo_payload(settings, config, **CATALOG_ARGS)


def _committed(settings: DemandSettings) -> dict:
    return json.loads((settings.reports_dir / "metrics.json").read_text())["_multistep"]


def _day(iso: str) -> date:
    return date.fromisoformat(iso)


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_payload_shape(payload: dict) -> None:
    assert payload["schema_version"] == PAYLOAD_SCHEMA_VERSION == 3
    assert payload["demo"] == "forecast-workbench"
    assert payload["project"] == "02-demand-forecasting"
    assert payload["protocol"] == "direct_multihorizon_v1"
    for key in (
        "catalog",
        "class_scoreboard",
        "horizon_growth",
        "bands",
        "decision",
        "headline",
        "catalog_summary",
        "evaluation_metadata",
        "dataset_metadata",
    ):
        assert key in payload
    assert len(payload["catalog"]) == 6
    entry = payload["catalog"][0]
    assert {
        "series_id",
        "label",
        "country",
        "product",
        "demand_class",
        "adi",
        "cv2",
        "model_used",
        "origins",
    } <= set(entry)
    assert entry["demand_class"] in ("erratic", "lumpy")
    assert len(entry["origins"]) == 3
    origin = entry["origins"][0]
    assert origin["horizons"] == HORIZONS
    assert len(origin["models"]["zero"]["y_pred"]) == len(HORIZONS)
    assert len(origin["models"]["routed"]["y_pred"]) == len(HORIZONS)
    assert len(origin["models"]["floor"]["y_pred"]) == len(HORIZONS)
    # champion_hgb exists for erratic series only; its curve is the boosted
    # direct HGB, which IS the routed curve only when the router kept the
    # series on direct_hgb (wave 20: erratic series may route to the
    # peak-capable ML candidates instead)
    for e in payload["catalog"]:
        has_champ = "champion_hgb" in e["origins"][0]["models"]
        assert has_champ == (e["demand_class"] == "erratic")
        if has_champ and e["model_used"] == "direct_hgb":
            assert (
                e["origins"][0]["models"]["champion_hgb"]["y_pred"]
                == e["origins"][0]["models"]["routed"]["y_pred"]
            )


def test_class_quotas_keep_every_erratic_series(payload: dict) -> None:
    by_class = payload["catalog_summary"]["by_class"]
    assert by_class["erratic"] == 2  # the fixture has exactly 2 erratic series
    assert by_class["lumpy"] == 4
    # every catalog entry honours the committed per-series routing choice;
    # lumpy series never sit on the boosted direct HGB (sparse pool has no
    # direct_hgb), erratic series choose among direct_hgb + the ML candidates
    for e in payload["catalog"]:
        if e["demand_class"] == "lumpy":
            assert e["model_used"] != "direct_hgb"
        else:
            assert e["model_used"] in ("direct_hgb", "hgb_tweedie", "hurdle_hgb")


# ---------------------------------------------------------------------------
# Cutoff truth: no gap anywhere
# ---------------------------------------------------------------------------


def test_origin_contiguity_no_gap(payload: dict, demo_context) -> None:
    """History ends the day BEFORE the origin; actuals start the day AFTER —
    contiguous, no embargo gap (protocol v2: the window abuts the origin)."""
    _settings, _config, panel = demo_context
    dates, series_ids, units = panel_matrix(panel)
    date_strs = [str(d)[:10] for d in dates]
    units_of = dict(zip(series_ids, units.T, strict=True))
    scored_dates = [o["origin_date"] for o in payload["catalog_summary"]["origins"]]
    assert scored_dates == sorted(scored_dates)
    for entry in payload["catalog"]:
        hist_all = {d: y for d, y in zip(date_strs, units_of[entry["series_id"]], strict=True)}
        for origin in entry["origins"]:
            o = _day(origin["origin_date"])
            # history: ends at origin-1, daily-contiguous, matches the panel
            assert _day(origin["history"]["dates"][-1]) == o - timedelta(days=1)
            hist_dates = origin["history"]["dates"]
            for a, b in itertools.pairwise(hist_dates):
                assert _day(b) - _day(a) == timedelta(days=1)
            for d, y in zip(origin["history"]["dates"], origin["history"]["y"], strict=True):
                assert hist_all[d] == y
            # actuals: start at origin+1, daily-contiguous through origin+14
            assert _day(origin["actuals"]["dates"][0]) == o + timedelta(days=1)
            assert _day(origin["actuals"]["dates"][-1]) == o + timedelta(days=14)
            act_dates = origin["actuals"]["dates"]
            for a, b in itertools.pairwise(act_dates):
                assert _day(b) - _day(a) == timedelta(days=1)
            for d, y in zip(origin["actuals"]["dates"], origin["actuals"]["y"], strict=True):
                assert hist_all[d] == y


def test_origins_are_the_three_most_recent_scored(payload: dict, demo_context) -> None:
    settings, _config, panel = demo_context
    dates, _sids, _units = panel_matrix(panel)
    test = split_origins(multistep_origin_indices(len(dates), MS_CONFIG), MS_CONFIG)[1]
    expected = [str(dates[o])[:10] for o in test[-3:]]
    got = [o["origin_date"] for o in payload["catalog_summary"]["origins"]]
    assert got == expected
    committed = _committed(settings)
    assert expected == committed["origins"]["test_dates"][-3:]
    for origin in payload["catalog_summary"]["origins"]:
        start, end = origin["horizon_window"]
        assert _day(start) - _day(origin["origin_date"]) == timedelta(days=1)
        assert _day(end) - _day(origin["origin_date"]) == timedelta(days=14)


# ---------------------------------------------------------------------------
# Routing honesty
# ---------------------------------------------------------------------------


def test_model_used_matches_committed_routing(payload: dict, demo_context) -> None:
    settings, _config, _panel = demo_context
    committed = _committed(settings)["routing"]["method_choices"]
    for entry in payload["catalog"]:
        assert entry["model_used"] == committed[entry["series_id"]]


def test_lumpy_routed_curve_matches_statistical_refit(
    payload: dict, demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame]
) -> None:
    """The routed lumpy curve equals the committed method's flat forecast,
    re-fit by hand on the as-of-origin training history (drift = a bug)."""
    _settings, _config, panel = demo_context
    dates, series_ids, units = panel_matrix(panel)
    idx = {s: i for i, s in enumerate(series_ids)}
    for entry in payload["catalog"]:
        if entry["demand_class"] != "lumpy" or entry["model_used"] in (
            "zero",
            "seasonal_naive",
            "hgb_tweedie",
            "hurdle_hgb",  # ML-routed curves are model predictions, not flat re-fits
        ):
            continue
        i = idx[entry["series_id"]]
        for origin in entry["origins"]:
            o = date_str_to_index(dates, origin["origin_date"])
            hist = units[: o + 1, i]
            flat = statistical_forecast(entry["model_used"], hist, 14)
            want = [round(float(flat[h - 1]), 4) for h in HORIZONS]
            got = [max(v, 0.0) for v in origin["models"]["routed"]["y_pred"]]
            assert got == pytest.approx(want, abs=1e-4)


def date_str_to_index(dates: np.ndarray, iso: str) -> int:
    return int(np.searchsorted(dates.astype("datetime64[D]"), np.datetime64(iso)))


# ---------------------------------------------------------------------------
# Bands + shocks
# ---------------------------------------------------------------------------


def test_band_sanity(payload: dict) -> None:
    """Erratic rows carry the conformal p10/p90 (no negatives, no inversions,
    clamped around the point curve); lumpy rows carry P(sale) + a ladder."""
    for entry in payload["catalog"]:
        for origin in entry["origins"]:
            routed = origin["models"]["routed"]
            if entry["demand_class"] == "erratic":
                for key in ("p10", "p90"):
                    assert len(routed[key]) == len(HORIZONS)
                for lo, mid, hi in zip(routed["p10"], routed["y_pred"], routed["p90"], strict=True):
                    assert 0 <= lo <= mid <= hi
                band = origin["models"]["champion_hgb"]
                assert band["p10"] == routed["p10"] and band["p90"] == routed["p90"]
                assert "band" not in routed
            else:
                assert "p10" not in routed and "p90" not in routed
                sparse_band = routed["band"]
                assert 0.0 <= sparse_band["p_sale"] <= 1.0
                ladder = [sparse_band["ladder"][f"{lvl:.2f}"] for lvl in (0.5, 0.8, 0.9, 0.95)]
                assert ladder == sorted(ladder)
                assert all(v >= 0 for v in ladder)


def test_full_lattice_curves_cover_the_whole_window(payload: dict) -> None:
    """Revision 3.2: the committed lattice is the full h = 1..14 — every model
    curve carries one real direct-h point per window day (14 contiguous days,
    no display interpolation), and the per-h band entries exist at every h."""
    assert list(range(1, 15)) == HORIZONS
    for entry in payload["catalog"]:
        for origin in entry["origins"]:
            assert origin["horizons"] == list(range(1, 15))
            window = origin["actuals"]["dates"]
            assert len(window) == 14
            for name, block in origin["models"].items():
                if "alias" in block:
                    continue  # candidate aliases share the routed curve
                assert len(block["y_pred"]) == 14, f"{name} curve is not full-lattice"
                for curve in block["shock"].values():
                    assert len(curve) == 14
            # the learner band exists at every h and stays clamped around the
            # point curve (sparse rows carry the P(sale)+ladder band instead)
            if entry["demand_class"] == "erratic":
                assert len(origin["models"]["routed"]["p10"]) == 14
                assert len(origin["models"]["routed"]["p90"]) == 14
            # the plotted daily path spans the whole window: one point per
            # actual day, dates identical to the window's
            for _name, block in origin["models"].items():
                if "alias" in block:
                    block = origin["models"]["routed"]
                path = [
                    (origin["actuals"]["dates"][h - 1], block["y_pred"][i])
                    for i, h in enumerate(origin["horizons"])
                ]
                assert [d for d, _y in path] == window
                assert len(path) == 14


def test_shock_blocks_are_present_and_sane(payload: dict, demo_context) -> None:
    _settings, _config, panel = demo_context
    dates, series_ids, units = panel_matrix(panel)
    idx = {s: i for i, s in enumerate(series_ids)}
    for entry in payload["catalog"]:
        for origin in entry["origins"]:
            for _model, block in origin["models"].items():
                if "alias" in block:
                    continue  # candidate aliases share the routed curve + shocks
                assert set(block["shock"]) == {f"{s:g}" for s in SHOCK_FACTORS}
                for curve in block["shock"].values():
                    assert len(curve) == len(HORIZONS)
                    assert all(v >= 0 for v in curve)
            # zero stays zero under every shock; the seasonal-naive floor reads
            # reference days inside the shocked week for every lattice h, so
            # its shocked curve is exactly s x the base curve
            floor = origin["models"]["floor"]
            for s_key, curve in floor["shock"].items():
                s = float(s_key)
                assert curve == pytest.approx([s * v for v in floor["y_pred"]], abs=1e-4)
            # statistical re-fit consistency: a lumpy routed curve under shock
            # equals the method re-fit on the shocked history
            if entry["demand_class"] == "lumpy" and entry["model_used"] not in (
                "zero",
                "seasonal_naive",
                "hgb_tweedie",
                "hurdle_hgb",  # ML curves re-predict through fitted trees, not re-fits
            ):
                i = idx[entry["series_id"]]
                o = date_str_to_index(dates, origin["origin_date"])
                hist = units[: o + 1, i].copy()
                for s_key, curve in origin["models"]["routed"]["shock"].items():
                    s = float(s_key)
                    shocked = hist.copy()
                    shocked[-7:] *= s
                    flat = statistical_forecast(entry["model_used"], shocked, 14)
                    want = [round(float(flat[h - 1]), 4) for h in HORIZONS]
                    assert [max(v, 0.0) for v in curve] == pytest.approx(want, abs=1e-4)


# ---------------------------------------------------------------------------
# Experiment-wide blocks match the committed metrics
# ---------------------------------------------------------------------------


def test_scoreboard_matches_committed(payload: dict, demo_context) -> None:
    settings, _config, _panel = demo_context
    ms = _committed(settings)
    for cls, board in payload["class_scoreboard"].items():
        committed_cls = ms["headline_per_class"][cls]
        assert board["n_series"] == committed_cls["n_series"]
        for h in ("h7", "h14"):
            if h not in committed_cls:
                continue
            assert board["mae"][h]["model"] == pytest.approx(
                committed_cls[h]["champion_mae"], abs=1e-9
            )
            assert board["mae"][h]["floor"] == pytest.approx(
                committed_cls[h]["floor_mae"], abs=1e-9
            )
            assert board["gap_bootstrap"][h] == committed_cls[h]["champion_vs_floor"]
            assert board["vs_zero_bootstrap"][h] == committed_cls[h]["champion_vs_naive_zero"]
            beats = board["beats_floor"][h]
            assert 0 <= beats["count"] <= beats["n"]
            assert beats["share"] == pytest.approx(beats["count"] / beats["n"], abs=1e-4)
        assert board["routing_effect"] == ms["routing"]["per_class"][cls]


def test_scoreboard_candidates_and_peak_capture(payload: dict, demo_context) -> None:
    """Revision 3.1: the peak-capable candidates the router actually selected
    surface per-series, the scoreboard carries their committed rows, and the
    peak-capture block lands per class — all equal to the committed metrics."""
    settings, _config, _panel = demo_context
    ms = _committed(settings)
    assert payload["payload_revision"] == "3.2"
    assert payload["peak_capture"] == ms["peak_capture"]
    for e in payload["catalog"]:
        models = e["origins"][0]["models"]
        for cand in ("hgb_tweedie", "hurdle_hgb"):
            if e["model_used"] == cand:
                # the router selected the candidate: an alias of the routed curve
                assert models[cand] == {"alias": "routed"}
            else:
                assert cand not in models
    for cls, board in payload["class_scoreboard"].items():
        committed_cls = ms["headline_per_class"][cls]
        for cand in ("hgb_tweedie", "hurdle_hgb"):
            for h in ("h7", "h14"):
                if h not in committed_cls or committed_cls[h].get(f"{cand}_mae") is None:
                    continue
                row = board["candidates"][cand][h]
                assert row["mae"] == pytest.approx(committed_cls[h][f"{cand}_mae"], abs=1e-9)
                assert row["vs_routed"] == committed_cls[h][f"{cand}_vs_routed"]
                assert row["vs_zero"] == committed_cls[h][f"{cand}_vs_zero"]
    assert payload["catalog_summary"]["peak_capable_candidates"] == ms["peak_capable_candidates"]


def test_horizon_growth_and_bands_match_committed(payload: dict, demo_context) -> None:
    settings, _config, _panel = demo_context
    ms = _committed(settings)
    growth = payload["horizon_growth"]
    assert growth["horizons"] == HORIZONS
    assert growth["pooled"] == ms["horizon_growth"]["pooled"]
    for h in HORIZONS:
        committed_mase = ms["per_horizon"][str(h)]["champion"]["mase"]
        if np.isfinite(committed_mase):
            assert growth["mase"]["champion"][str(h)] == pytest.approx(committed_mase, abs=1e-9)
        else:
            assert growth["mase"]["champion"][str(h)] is None
    prob = json.loads((settings.reports_dir / "probabilistic.json").read_text())["multistep"]
    assert payload["bands"]["per_horizon"] == prob["per_horizon"]
    assert payload["bands"]["conformal_widths_by_h"] == prob["conformal_widths_by_h"]
    assert payload["bands"]["pooled_coverage"] == prob["pooled_coverage"]


def test_decision_block_matches_committed(payload: dict, demo_context) -> None:
    settings, _config, _panel = demo_context
    committed = _committed(settings)["decision_metric"]
    decision = payload["decision"]
    assert decision["simulation"] is True
    assert decision["cost_assumptions"] == committed["cost_assumptions"]
    assert decision["per_class"] == committed["per_class"]
    assert all(isinstance(t, str) for t in decision["tau_grid"])
    # the τ→quantile mapping is monotone non-decreasing in τ (quantiles)
    for _cls, per_policy in decision["quantile_map"].items():
        for policy in ("champion", "floor"):
            for h, taus in per_policy[policy].items():
                values = [taus[t] for t in decision["tau_grid"]]
                assert values == sorted(values)
                assert int(h) in HORIZONS


# ---------------------------------------------------------------------------
# Determinism, size, drift guards, roundtrip
# ---------------------------------------------------------------------------


def test_deterministic(payload: dict, demo_context) -> None:
    settings, config, _panel = demo_context
    again = build_demo_payload(settings, config, **CATALOG_ARGS)
    assert again == payload


def test_size_headroom_for_full_catalog(payload: dict) -> None:
    """The 6-series fixture payload scaled to 100 series x 3 origins must fit
    the cap with headroom (the UCI regeneration enforces the cap itself).
    Experiment-wide blocks are fixed-size — only the per-series bytes scale."""
    size = len((json.dumps(payload, indent=2) + "\n").encode())
    fixed_keys = (
        "class_scoreboard",
        "horizon_growth",
        "peak_capture",
        "bands",
        "decision",
        "headline",
        "catalog_summary",
        "evaluation_metadata",
        "dataset_metadata",
    )
    fixed = len((json.dumps({k: payload[k] for k in fixed_keys}, indent=2)).encode())
    per_series = (size - fixed) / len(payload["catalog"])
    projected = per_series * 100 + fixed
    # the real UCI regeneration enforces the cap at write time; here we only
    # sanity-check the per-series cost does not blow past it at 100 series
    assert projected <= SIZE_CAP_BYTES, f"projected {projected:.0f} bytes over cap"


def _tamper(settings: DemandSettings, name: str, fn) -> None:
    path = settings.reports_dir / name
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def test_drift_guard_raises_on_tampered_overall_mae(demo_context) -> None:
    settings, config, _panel = demo_context
    _tamper(
        settings,
        "metrics.json",
        lambda d: d["_multistep"]["overall_mae_test"].update(routed=0.0),
    )
    with pytest.raises(ValueError, match="overall_mae_test"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_drift_guard_raises_on_tampered_origins(demo_context) -> None:
    settings, config, _panel = demo_context
    _tamper(
        settings,
        "metrics.json",
        lambda d: d["_multistep"]["origins"]["dates"].__setitem__(0, "1999-01-01"),
    )
    with pytest.raises(ValueError, match="origin plan"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_drift_guard_raises_on_tampered_routing(demo_context) -> None:
    settings, config, _panel = demo_context
    _tamper(
        settings,
        "metrics.json",
        lambda d: d["_multistep"]["routing"]["method_choices"].clear(),
    )
    with pytest.raises(ValueError, match="routing"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_drift_guard_raises_on_tampered_widths(demo_context) -> None:
    settings, config, _panel = demo_context
    _tamper(
        settings,
        "probabilistic.json",
        lambda d: d["multistep"]["conformal_widths_by_h"].update({"7": 999.0}),
    )
    with pytest.raises(ValueError, match="conformal_widths"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_write_demo_payload_roundtrip(demo_context) -> None:
    settings, config, _panel = demo_context
    out = write_demo_payload(settings, config, **CATALOG_ARGS)
    assert out.name == "demo_payload.json"
    on_disk = json.loads(out.read_text())
    assert on_disk == build_demo_payload(settings, config, **CATALOG_ARGS)
