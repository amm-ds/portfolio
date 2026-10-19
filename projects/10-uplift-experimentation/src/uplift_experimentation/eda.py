"""EDA figure: arm sizes, outcome rates and covariate balance per segment."""

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme, style_runs

from uplift_experimentation.data import segment_summary

RATE_COLORS = {"visit_rate": "#38bdf8", "conversion_rate": "#2dd4bf"}


def eda_segment_profile_figure(df: pl.DataFrame) -> go.Figure:
    """Three-arm profile: sizes, outcome rates, and pre-period spend balance."""
    summary = segment_summary(df)
    segments = summary["segment"].to_list()

    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=("Arm sizes", "Outcome rates by arm", "Mean prior-year spend"),
        horizontal_spacing=0.12,
    )
    fig.add_bar(
        x=segments,
        y=summary["n"].to_list(),
        name="customers",
        marker_color="#a78bfa",
        row=1,
        col=1,
    )
    for col, label in (("visit_rate", "visit rate"), ("conversion_rate", "conversion rate")):
        fig.add_bar(
            x=segments,
            y=summary[col].to_list(),
            name=label,
            marker_color=RATE_COLORS[col],
            row=1,
            col=2,
        )
    fig.add_bar(
        x=segments,
        y=summary["mean_history"].to_list(),
        name="mean spend (pre-period)",
        marker_color="#fbbf24",
        row=1,
        col=3,
    )
    fig.update_yaxes(title_text="customers", row=1, col=1)
    fig.update_yaxes(title_text="rate", row=1, col=2)
    fig.update_yaxes(title_text="USD (prior year)", row=1, col=3)
    apply_theme(fig, width=1240, height=520)
    style_runs(fig)
    fig.update_layout(
        barmode="group",
        title="Three arms: sizes, outcome rates, prior spend",
    )
    add_takeaway(
        fig,
        "Hillstrom March 2008 — 64,000 customers, three arms; "
        "visit + conversion rates, prior spend",
    )
    return fig
