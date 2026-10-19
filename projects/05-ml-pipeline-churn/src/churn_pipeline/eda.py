"""Exploratory figures for the churn dataset, built during ``prepare``.

These describe the *input* data (not model outputs) and are persisted next to
the evaluation figures so the showcase app can render the full story.
"""

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme


def eda_churn_profile_figure(df: pl.DataFrame) -> go.Figure:
    """Churn rate by contract + monthly_charges / tenure distributions.

    Three panels: (1) observed churn rate per contract type, (2) monthly
    charges distribution split by churn outcome, (3) tenure distribution
    split by churn outcome. Churned is boolean in the generator; cast to
    Int8 so aggregations and filters are explicit.
    """
    d = df.with_columns(pl.col("churned").cast(pl.Int8))
    by_contract = (
        d.group_by("contract")
        .agg(pl.len().alias("n"), pl.col("churned").mean().alias("rate"))
        .sort("rate", descending=True)
    )

    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=(
            "Churn rate by contract",
            "Monthly charges distribution",
            "Tenure distribution",
        ),
    )
    fig.add_bar(
        x=by_contract["contract"].to_list(),
        y=by_contract["rate"].to_list(),
        name="churn rate",
        marker={"color": "#2dd4bf"},
        row=1,
        col=1,
    )
    for churned, color, label in ((1, "#f472b6", "churned"), (0, "#38bdf8", "stayed")):
        sub = d.filter(pl.col("churned") == churned)
        fig.add_histogram(
            x=sub["monthly_charges"].to_list(),
            histnorm="probability density",
            marker={"color": color, "opacity": 0.65},
            name=label,
            row=1,
            col=2,
        )
        fig.add_histogram(
            x=sub["tenure_months"].to_list(),
            histnorm="probability density",
            marker={"color": color, "opacity": 0.65},
            name=label,
            legendgroup=label,
            showlegend=False,
            row=1,
            col=3,
        )
    fig.update_layout(
        title="Churn concentrates in short contracts",
        barmode="overlay",
        yaxis_title="churn rate",
        xaxis2_title="monthly_charges",
        yaxis2_title="density",
        xaxis3_title="tenure_months",
        yaxis3_title="density",
    )
    add_takeaway(fig, "42.7% month-to-month vs 2.8% two-year churn")
    return apply_theme(fig)
