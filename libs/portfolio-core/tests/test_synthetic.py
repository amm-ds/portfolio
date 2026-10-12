import polars as pl
from portfolio_core import synthetic


def test_retail_deterministic() -> None:
    a = synthetic.retail_hierarchy(seed=7)
    b = synthetic.retail_hierarchy(seed=7)
    c = synthetic.retail_hierarchy(seed=8)
    assert a.equals(b)
    assert not a.equals(c)
    assert a.height == 730 * 4 * 6
    assert set(a.columns) == {"date", "store", "product", "units", "price"}


def test_telemetry_shapes_and_anomaly_rate() -> None:
    df = synthetic.telemetry(seed=1, n=2000, anomaly_rate=0.05)
    assert df.height == 2000
    assert df.filter(pl.col("is_anomaly")).height == 100
    assert max(df.get_column("cpu").to_list()) <= 100


def test_churn_has_deliberate_messiness() -> None:
    df = synthetic.churn(seed=1, n=3000)
    assert df.height == 3000
    assert df.get_column("age").is_nan().sum() > 0
    assert max(df.get_column("monthly_charges").to_list()) > 1000  # planted outlier
    assert set(df["contract"].unique()) == {"month-to-month", "one-year", "two-year"}
