"""EDA figure tests on the tiny synthetic frame."""

import polars as pl
from churn_pipeline.eda import eda_churn_profile_figure
from portfolio_core import synthetic


def test_eda_churn_profile_panels() -> None:
    df = synthetic.churn(seed=7, n=300)
    fig = eda_churn_profile_figure(df)
    # 3 panels: contract-rate bar + 2 histograms across 2 churn classes = 5 traces
    assert len(fig.data) == 5
    names = [d.name for d in fig.data]
    assert "churned" in names and "stayed" in names
    # contract panel shows one bar per contract level
    bar = next(d for d in fig.data if d.type == "bar")
    assert len(bar.x) == df["contract"].n_unique()


def test_eda_handles_boolean_churn() -> None:
    df = pl.DataFrame(
        {
            "age": [30.0, 40.0],
            "tenure_months": [1.0, 24.0],
            "monthly_charges": [50.0, 100.0],
            "support_calls": [0.0, 2.0],
            "contract": ["one-year", "two-year"],
            "churned": [False, True],
        }
    )
    fig = eda_churn_profile_figure(df)
    assert len(fig.data) == 5
