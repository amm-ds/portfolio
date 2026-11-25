from dynamic_pricing.config import ProjectConfig
from portfolio_core.dq import DQReport


def test_scaffold_loads_default_config() -> None:
    assert ProjectConfig().seed == 42


def test_scaffold_supports_calibration_quality_report() -> None:
    report = DQReport(dataset="m5", n_rows=1)
    report.check_null_rate("sell_price", null_rate=0.0, max_null_rate=0.0)
    report.check_range("sell_price", 1.0, 1.0, 0.0, 2.0)
    report.check_freshness("2016-04-24", "2011-01-29")
    report.raise_if_failed()

    assert report.passed
    assert report.n_failed == 0
    assert "sell_price" in report.to_markdown()
