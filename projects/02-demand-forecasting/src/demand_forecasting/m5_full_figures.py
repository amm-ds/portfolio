"""M5 FULL-panel story figures — standalone builder (offline).

``build-figures-m5-full`` reads ONLY the committed artifacts
(``reports_m5_full/metrics.json``, ``catalog_forecasts.parquet``,
``catalog_meta.json`` and the demo payload for the 56-day history tails) and
writes the Plotly figures the story.yaml references into
``reports_m5_full/figures/`` — no re-running anything, same contract as
:mod:`demand_forecasting.m5_full_report`.

Figure ids (referenced by story.yaml, prefix-free — the showcase API resolves
them through ``reports_m5_full/figures/`` first):

- ``m5_full_per_level_wrmsse`` — per-level official WRMSSE on the test window:
  ensemble vs seasonal-naive floor vs best single candidate.
- ``m5_full_sample_series`` — three catalog series (top-units, hardest
  intermittent, mid-volume): 56-day history + 28-day actual + ensemble curve
  with the member-envelope band.
- ``m5_full_candidate_ranking`` — all 8 candidates ranked by official WRMSSE.
- ``m5_full_pooling_panel`` — the pooling story on one top-units series:
  56-day history + 28-day actual with the global, pooled, and blend curves.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json

from demand_forecasting.m5_full import CANDIDATES
from demand_forecasting.m5_full_report import (
    DISPLAY,
    fig_per_level_bars,
    load_artifacts,
)
from demand_forecasting.m5_track import NAIVE

logger = get_logger(__name__)

#: the three sample series: one top-units, one hardest-intermittent, one
#: mid-volume (ranks from catalog_meta.json, kept as literals so a catalog
#: re-pick fails here loudly instead of silently shipping other series).
SAMPLE_SERIES: tuple[tuple[str, str], ...] = (
    ("FOODS_3_090_CA_3", "top-units (rank 0 by last-28-day units)"),
    ("HOUSEHOLD_1_336_CA_3", "hardest intermittent (ADI 105.9, rank 0)"),
    ("HOUSEHOLD_1_110_TX_2", "mid-volume (rank 260 of 30,490, smooth dense)"),
)

PAYLOAD_NAME = "demo_payload.json"


def fig_sample_series(
    catalog: pd.DataFrame, cat_meta: dict[str, Any], payload: dict[str, Any]
) -> go.Figure:
    """56-day history + 28-day actual + ensemble curve for the three samples.

    The history tails ship only in the demo payload (sliced from the raw
    panel); the scored window (actuals, curves, band) comes from the committed
    ``catalog_forecasts.parquet`` — the payload's curves are verbatim copies
    of it (self-check drift 0.0), so the two join exactly.
    """
    history_of = {e["series_id"]: e["windows"]["history"] for e in payload["catalog"]}
    ranks = {d["unique_id"]: d for d in cat_meta["series"]}
    n = len(SAMPLE_SERIES)
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        subplot_titles=[
            f"{sid} — {label} · {ranks[sid]['units_last_28d']:.0f} units/28d, "
            f"{ranks[sid]['class']} (ADI {ranks[sid]['adi']:.2f})"
            for sid, label in SAMPLE_SERIES
        ],
        vertical_spacing=0.08,
    )
    origin = cat_meta["forecast_window"][0]
    x_hist = [f"d{i - 55}" for i in range(56)]
    x_fcst = [str(d.date()) for d in sorted(catalog["ds"].unique())]
    colors = {"history": "#94a3b8", "actual": "#f472b6", "convex_ensemble": "#fbbf24"}
    shown: set[str] = set()
    for i, (sid, _label) in enumerate(SAMPLE_SERIES, start=1):
        row = catalog[catalog["unique_id"] == sid].sort_values("ds")
        for key, y in (
            ("history", history_of[sid]),
            ("actual", list(row["actual"])),
            ("convex_ensemble", list(row["convex_ensemble"])),
        ):
            show = key not in shown
            shown.add(key)
            fig.add_scatter(
                x=x_hist if key == "history" else x_fcst,
                y=y,
                name=key,
                mode="lines",
                line={"color": colors[key], "width": 2.5 if key == "convex_ensemble" else 1.5},
                showlegend=show,
                row=i,
                col=1,
            )
        fig.add_scatter(
            x=x_fcst,
            y=list(row["band_lo"]),
            name="member envelope lo",
            mode="lines",
            line={"color": "#fbbf24", "width": 0.5, "dash": "dot"},
            showlegend=False,
            row=i,
            col=1,
        )
        fig.add_scatter(
            x=x_fcst,
            y=list(row["band_hi"]),
            name="member envelope hi",
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(251, 191, 36, 0.12)",
            line={"color": "#fbbf24", "width": 0.5, "dash": "dot"},
            showlegend=False,
            row=i,
            col=1,
        )
    fig.update_layout(
        title=(
            f"Three catalog series at the scored-once test origin {origin}: "
            "history, actuals, ensemble curve"
        )
    )
    return add_takeaway(
        apply_theme(fig, height=300 * n),
        "the ensemble tracks the weekly shape on dense volume, stays honest near "
        "zero on the hardest intermittent series, and the member envelope "
        "(per-day min/max of the blend members) is an envelope — not a "
        "calibrated interval",
    )


def fig_candidate_ranking(metrics: dict[str, Any]) -> go.Figure:
    """All 8 candidates ranked by official WRMSSE on the test window."""
    test = metrics["test"]
    ranked = sorted(CANDIDATES, key=lambda c: test[c]["official_wrmsse"])
    vals = [test[c]["official_wrmsse"] for c in ranked]
    rel = [100.0 * (v / test[NAIVE]["official_wrmsse"] - 1.0) for v in vals]
    fig = go.Figure(
        data=go.Bar(
            x=[DISPLAY[c] for c in ranked],
            y=vals,
            text=[f"{v:.4f} ({r:+.1f}%)" for v, r in zip(vals, rel, strict=True)],
            textposition="outside",
            marker_color=[
                "#64748b" if c == NAIVE else "#fbbf24" if c == "convex_ensemble" else "#2dd4bf"
                for c in ranked
            ],
        )
    )
    fig.update_layout(
        title="Official WRMSSE on the competition window, ranked (42,840 nodes)",
        yaxis={"range": [0, max(vals) * 1.15]},
    )
    return add_takeaway(
        apply_theme(fig),
        f"the stability-screened convex ensemble leads at {vals[0]:.4f}; every "
        f"pooled arm and the Tweedie variant beat the global model — pooling "
        f"wins at full scale, the inverse of the subset-era finding",
    )


def fig_pooling_panel(
    catalog: pd.DataFrame,
    cat_meta: dict[str, Any],
    payload: dict[str, Any],
    metrics: dict[str, Any],
) -> go.Figure:
    """The pooling story on one top-units series: global vs pooled vs blend.

    The series is the sample figure's top-units pick (history tails ship in
    the demo payload; the scored window comes from the committed
    ``catalog_forecasts.parquet``). On one erratic series the fits sit
    within noise of each other — the pooling edge is a panel-level
    property, and the official WRMSSE over all 42,840 nodes is where it
    shows.
    """
    sid, _label = SAMPLE_SERIES[0]
    history_of = {e["series_id"]: e["windows"]["history"] for e in payload["catalog"]}
    rank = {d["unique_id"]: d for d in cat_meta["series"]}[sid]
    row = catalog[catalog["unique_id"] == sid].sort_values("ds")
    origin = cat_meta["forecast_window"][0]
    x_hist = [f"d{i - 55}" for i in range(56)]
    x_fcst = [str(d.date()) for d in row["ds"]]
    fig = go.Figure()
    for name, y, color, dash, width in (
        ("history", history_of[sid], "#94a3b8", "solid", 1.5),
        ("actual", list(row["actual"]), "#f472b6", "solid", 2.0),
        ("lgbm (global)", list(row["lgbm"]), "#38bdf8", "dash", 2.0),
        ("lgbm_pool_store (pooled)", list(row["lgbm_pool_store"]), "#2dd4bf", "solid", 2.0),
        ("convex_ensemble (blend)", list(row["convex_ensemble"]), "#fbbf24", "solid", 2.5),
    ):
        fig.add_scatter(
            x=x_hist if name == "history" else x_fcst,
            y=y,
            name=name,
            mode="lines",
            line={"color": color, "width": width, "dash": dash},
        )
    fig.update_layout(
        title=(
            f"Top-units series {sid} ({rank['units_last_28d']:.0f} units/28d) at the "
            f"scored-once test origin {origin}: global vs pooled vs blend"
        )
    )
    test = metrics["test"]
    return add_takeaway(
        apply_theme(fig),
        f"on one erratic series the fits sit within noise of each other — "
        f"the pooling edge is a panel-level property; official WRMSSE over "
        f"all 42,840 nodes: "
        f"{test['lgbm']['official_wrmsse']:.4f} global vs "
        f"{test['lgbm_pool_store']['official_wrmsse']:.4f} pooled vs "
        f"{test['convex_ensemble']['official_wrmsse']:.4f} blend",
    )


def build_figures_full(reports_dir: Path) -> Path:
    """Write figures/*.html + *.json for the story from committed artifacts."""
    reports_dir = Path(reports_dir)
    art = load_artifacts(reports_dir)
    metrics = art["metrics"]
    from demand_forecasting.m5_full_catalog import CATALOG_FORECASTS_NAME, CATALOG_META_NAME

    frame = pd.read_parquet(reports_dir / CATALOG_FORECASTS_NAME)
    cat_meta = json.loads((reports_dir / CATALOG_META_NAME).read_text())
    payload = json.loads((reports_dir / PAYLOAD_NAME).read_text())

    figures: dict[str, go.Figure] = {
        "m5_full_per_level_wrmsse": fig_per_level_bars(metrics),
        "m5_full_sample_series": fig_sample_series(frame, cat_meta, payload),
        "m5_full_candidate_ranking": fig_candidate_ranking(metrics),
        "m5_full_pooling_panel": fig_pooling_panel(frame, cat_meta, payload, metrics),
    }
    figures_dir = reports_dir / "figures"
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")
    logger.info("m5 full figures -> %s", figures_dir)
    return figures_dir
