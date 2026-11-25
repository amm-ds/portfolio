"""E2-9 figures and standalone report rebuilt without sealed policy execution."""

import json
import math
import tempfile
from pathlib import Path
from typing import Any, cast

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.plotting import (
    CATEGORICAL_PALETTE,
    add_takeaway,
    apply_theme,
    save_html,
    save_json,
)
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.report import ReportBuilder

POLICY_IDS = ("B0", "B1", "B2", "B3", "RL", "UB")
TIMES = chr(0x00D7)
RHO = chr(0x03C1)
MINUS = chr(0x2212)
POLICY_LABELS = {
    "B0": "B0 · reference",
    "B1": f"B1 · static 1.30{TIMES}",
    "B2": "B2 · markdown",
    "B3": "B3 · Thompson",
    "RL": "RL · masked PPO",
    "UB": "UB · fluid ceiling",
}
COLORS = dict(zip(POLICY_IDS, CATEGORICAL_PALETTE, strict=True))


def _padded_range(lower: float, upper: float, *, minimum_pad: float = 0.01) -> list[float]:
    span = max(upper - lower, minimum_pad)
    pad = max(0.08 * span, minimum_pad)
    return [math.floor((lower - pad) * 100.0) / 100.0, math.ceil((upper + pad) * 100.0) / 100.0]


def profit_vs_baselines(metrics: dict[str, Any]) -> go.Figure:
    """Sealed mean profit with episode-bootstrap mean intervals."""
    policies = metrics["test"]["policies"]
    means = [policies[policy]["mean_normalised_profit"] for policy in POLICY_IDS]
    lo = [policies[policy]["mean_normalised_profit_ci95"][0] for policy in POLICY_IDS]
    hi = [policies[policy]["mean_normalised_profit_ci95"][1] for policy in POLICY_IDS]
    labels = [POLICY_LABELS[policy] for policy in POLICY_IDS]
    fig = go.Figure()
    for policy, label, mean, lower, upper in zip(POLICY_IDS, labels, means, lo, hi, strict=True):
        fig.add_scatter(
            x=[mean],
            y=[label],
            mode="markers",
            name=label,
            marker={"color": COLORS[policy], "size": 13},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": [upper - mean],
                "arrayminus": [mean - lower],
                "color": COLORS[policy],
                "thickness": 2,
                "width": 5,
            },
            hovertemplate=(
                "%{x:.6f}<br>episode-bootstrap 95% CI ["
                f"{lower:.6f}, {upper:.6f}]<extra>{label}</extra>"
            ),
            showlegend=False,
        )
    comparator_mean = policies[metrics["primary"]["comparator"]]["mean_normalised_profit"]
    fig.add_vline(
        x=comparator_mean,
        line={"color": COLORS["B1"], "dash": "dash", "width": 1.5},
        annotation_text="locked B1 comparator",
        annotation_position="top left",
    )
    apply_theme(fig, height=570)
    fig.update_layout(
        title="Sealed test profit — the static comparator stays ahead",
        xaxis_title="mean normalised episode profit (higher is better)",
        yaxis={"categoryorder": "array", "categoryarray": list(reversed(labels))},
        margin={"l": 180, "r": 70, "t": 110, "b": 70},
    )
    fig.update_xaxes(range=_padded_range(min(lo), max(hi)))
    primary = metrics["primary"]
    add_takeaway(
        fig,
        f"1,000 sealed episodes; RL lift vs B1 = {primary['relative_lift_pct']:.2f}%. "
        "Whiskers are per-policy episode-bootstrap 95% intervals, not the paired P1 interval.",
    )
    return fig


def price_traces(episodes: dict[str, Any]) -> go.Figure:
    """Three fixed-seed traces captured during the single sealed read."""
    indices = episodes["selection"]["price_trace_indices"]
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=[
            f"test episode {index} · {RHO} = {episodes['price_traces'][str(index)]['spec']['rho']}"
            for index in indices
        ],
    )
    for row, index in enumerate(indices, start=1):
        trace = episodes["price_traces"][str(index)]["policies"]
        for policy in ("B1", "RL"):
            rows = trace[policy]
            fig.add_scatter(
                x=[item["day"] for item in rows],
                y=[item["multiplier"] for item in rows],
                mode="lines",
                line={
                    "color": COLORS[policy],
                    "width": 2.5 if policy == "RL" else 2,
                    "dash": "solid" if policy == "RL" else "dash",
                    "shape": "hv",
                },
                name=POLICY_LABELS[policy],
                legendgroup=policy,
                showlegend=row == 1,
                hovertemplate="day %{x}<br>multiplier %{y:.2f}<extra></extra>",
                row=row,
                col=1,
            )
        fig.update_yaxes(title_text="price / reference", row=row, col=1, range=[0.68, 1.32])
    fig.update_xaxes(title_text="episode day", row=3, col=1, range=[0, 90], dtick=14)
    for row in (1, 2):
        fig.update_xaxes(range=[0, 90], dtick=14, row=row, col=1)
    apply_theme(fig, height=760)
    fig.update_layout(
        title="Price paths — learning does not translate into a B1 advantage",
        margin={"l": 90, "r": 150, "t": 120, "b": 70},
    )
    add_takeaway(
        fig,
        "Episodes 89, 654, and 773 were chosen by fixed seed before outcomes were inspected; "
        "paths come from the one sealed pass, not a rerun.",
    )
    return fig


def bound_share_by_rho(metrics: dict[str, Any]) -> go.Figure:
    """Grouped bound-attainment percentages across inventory-pressure buckets."""
    policies = metrics["test"]["policies"]
    rhos = ("0.7", "1.0", "1.3")
    fig = go.Figure()
    for policy in POLICY_IDS:
        values = [100.0 * policies[policy]["fluid_bound_share_by_rho"][rho] for rho in rhos]
        fig.add_bar(
            x=[f"{RHO} = {rho}" for rho in rhos],
            y=values,
            name=POLICY_LABELS[policy],
            marker={"color": COLORS[policy]},
            text=[f"{value:.1f}" for value in values],
            textposition="inside",
            hovertemplate="%{x}<br>%{y:.2f}% of fluid UB<extra></extra>",
        )
    fig.add_hline(y=100.0, line={"color": "#94a3b8", "dash": "dot", "width": 1})
    apply_theme(fig, height=610)
    fig.update_layout(
        title="Fluid-bound share by inventory pressure",
        xaxis_title=f"inventory pressure {RHO} (higher means scarcer inventory)",
        yaxis_title="mean profit / mean fluid UB (%)",
        barmode="group",
        margin={"l": 80, "r": 160, "t": 120, "b": 70},
    )
    fig.update_yaxes(range=[0, 110])
    add_takeaway(
        fig,
        f"Overall bound share: RL {policies['RL']['fluid_bound_share_pct']:.2f}%, "
        f"B1 {policies['B1']['fluid_bound_share_pct']:.2f}%. UB is a relaxed ceiling, "
        "not an executable competitor.",
    )
    return fig


def calibration_overview(calibration: list[dict[str, Any]]) -> go.Figure:
    """Distributions of all 600 calibrated M5 series without source rereads."""
    fields = (
        ("base", "recent mean daily units", CATEGORICAL_PALETTE[0]),
        ("k", "negative-binomial dispersion k", CATEGORICAL_PALETTE[1]),
        ("p_ref", "modal reference price", CATEGORICAL_PALETTE[2]),
    )
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=[field[1] for field in fields],
        horizontal_spacing=0.09,
    )
    for column, (field, title, color) in enumerate(fields, start=1):
        values = np.asarray([row[field] for row in calibration], dtype=np.float64)
        fig.add_histogram(
            x=values,
            name=title,
            marker={"color": color},
            nbinsx=40,
            showlegend=False,
            hovertemplate="%{x:.3f}<br>count %{y}<extra></extra>",
            row=1,
            col=column,
        )
        fig.update_xaxes(
            title_text=title,
            row=1,
            col=column,
            range=[0.0, float(values.max()) * 1.02],
        )
        fig.update_yaxes(title_text="series count", row=1, col=column)
    apply_theme(fig, height=570)
    fig.update_layout(
        title="Calibration overview — 600 M5-derived series",
        margin={"l": 75, "r": 50, "t": 120, "b": 95},
    )
    bases = np.asarray([row["base"] for row in calibration], dtype=np.float64)
    add_takeaway(
        fig,
        f"Window 2011-01-29 to 2016-04-24; median recent base demand {np.median(bases):.2f} "
        "units/day. Histograms retain the full observed ranges, including long right tails.",
    )
    return fig


def build_figures(
    metrics: dict[str, Any], episodes: dict[str, Any], calibration: list[dict[str, Any]]
) -> dict[str, go.Figure]:
    return {
        "profit_vs_baselines": profit_vs_baselines(metrics),
        "price_traces": price_traces(episodes),
        "bound_share_by_rho": bound_share_by_rho(metrics),
        "calibration_overview": calibration_overview(calibration),
    }


def run_figures(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    """Rebuild presentation artifacts only; never invoke the sealed evaluator."""
    del repo_root, params_path
    reports = project_root / "reports"
    metrics = cast(dict[str, Any], json.loads((reports / "metrics.json").read_text()))
    episodes = cast(dict[str, Any], json.loads((reports / "test_episodes.json").read_text()))
    calibration = cast(
        list[dict[str, Any]], json.loads((project_root / "data" / "calibration.json").read_text())
    )
    figures = build_figures(metrics, episodes, calibration)
    figures_dir = reports / "figures"
    for name, figure in figures.items():
        save_json(figure, figures_dir / f"{name}.json")
        save_html(figure, figures_dir / f"{name}.html")

    builder = ReportBuilder(
        title="15 · Dynamic Pricing with RL — sealed evaluation",
        figures_dir=figures_dir,
    )
    for policy in POLICY_IDS:
        values = metrics["test"]["policies"][policy]
        run_metrics = [
            MetricResult("mean_normalised_profit", values["mean_normalised_profit"]),
            MetricResult("mean_raw_gross_profit", values["mean_raw_gross_profit"]),
            MetricResult("fluid_bound_share_pct", values["fluid_bound_share_pct"]),
        ]
        if policy != "UB":
            run_metrics.append(MetricResult("violations", values["violations"]))
        builder.add_run(RunResult(name=POLICY_LABELS[policy], metrics=run_metrics))
    with tempfile.TemporaryDirectory(prefix=".report-builder-", dir=project_root) as temporary:
        report = builder.build(Path(temporary), figures=figures)
    primary = metrics["primary"]
    interval = primary["paired_difference"]
    report.add_html(
        "Pre-registered verdicts",
        f"<p><b>P1: FAIL.</b> RL relative lift vs B1 is {primary['relative_lift_pct']:.4f}%; "
        f"paired episode-bootstrap 95% CI for RL {MINUS} B1 is [{interval['lo']:.6f}, "
        f"{interval['hi']:.6f}]. <b>P2: PASS.</b> Every executable policy has zero "
        "violations on the 1,000-episode test set. P3 is context only.</p>",
    )
    report.write(reports / "report.html")
    return {
        "figures": list(figures),
        "report": "reports/report.html",
        "P1": metrics["verdicts"]["P1"],
        "P2": metrics["verdicts"]["P2"],
    }
