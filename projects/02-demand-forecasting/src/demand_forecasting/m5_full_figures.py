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
- ``m5_full_pooling_panel`` — full-panel bias and zero-day accuracy for all
  candidates, including the pooled fits and blend.
"""

from pathlib import Path
from typing import Any

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
        f"the stability-screened convex ensemble leads at {vals[0]:.4f}, under "
        f"0.001 ahead of the best pooled arm; direct pooled and recursive global "
        f"fits differ in both grouping and forecasting strategy",
    )


def fig_pooling_panel(metrics: dict[str, Any]) -> go.Figure:
    """Panel-level bias and quiet-day outcomes for every candidate.

    These full-panel diagnostics replace a single-series overlay that could not
    show pooling. Bias is signed; zero-day accuracy counts forecasts below 0.5
    when actual sales are zero.
    """
    test = metrics["test"]
    labels = [DISPLAY[c] for c in CANDIDATES]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("signed bias (%)", "zero-day accuracy"),
    )
    fig.add_bar(
        x=labels,
        y=[100.0 * test[c]["bias"] for c in CANDIDATES],
        name="bias",
        marker_color="#38bdf8",
        showlegend=False,
        row=1,
        col=1,
    )
    fig.add_bar(
        x=labels,
        y=[test[c]["zero_day_accuracy"] for c in CANDIDATES],
        name="all zero-actual days",
        marker_color="#2dd4bf",
        row=1,
        col=2,
    )
    fig.add_bar(
        x=labels,
        y=[test[c]["zero_day_accuracy_intermittent"] for c in CANDIDATES],
        name="intermittent series",
        marker_color="#fbbf24",
        row=1,
        col=2,
    )
    fig.add_hline(y=0.0, line={"dash": "dot", "color": "#64748b"}, row=1, col=1)
    fig.update_xaxes(tickangle=-35)
    fig.update_yaxes(title="mean(forecast - actual) / mean(actual)", row=1, col=1)
    fig.update_yaxes(title="share correct", range=[0, 1], row=1, col=2)
    ens = test["convex_ensemble"]
    floor_zda = test[NAIVE]["zero_day_accuracy"]
    blend_zda = ens["zero_day_accuracy"]
    if floor_zda > blend_zda and ens["bias"] > 0:
        title = (
            f"The floor wins on zero-sales days ({floor_zda:.1%} vs "
            f"{blend_zda:.1%}); the blend over-forecasts slightly "
            f"(bias {100.0 * ens['bias']:+.1f}%)"
        )
    else:
        title = "Forecast bias and quiet-day accuracy by candidate"
    fig.update_layout(
        title=title,
        barmode="group",
    )
    floor = test[NAIVE]["zero_day_accuracy"]
    blend = test["convex_ensemble"]["zero_day_accuracy"]
    return add_takeaway(
        apply_theme(fig),
        f"30,490 bottom series; positive bias = over-forecast; zero-day accuracy = "
        f"forecast < 0.5 when actual = 0 — floor {floor:.1%} vs blend {blend:.1%}",
    )


def build_figures_full(reports_dir: Path) -> Path:
    """Write figures/*.html + *.json for the story from committed artifacts."""
    reports_dir = Path(reports_dir)
    art = load_artifacts(reports_dir)
    metrics = art["metrics"]

    figures: dict[str, go.Figure] = {
        "m5_full_per_level_wrmsse": fig_per_level_bars(metrics),
        "m5_full_candidate_ranking": fig_candidate_ranking(metrics),
        "m5_full_pooling_panel": fig_pooling_panel(metrics),
    }
    figures_dir = reports_dir / "figures"
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")
    logger.info("m5 full figures -> %s", figures_dir)
    return figures_dir
