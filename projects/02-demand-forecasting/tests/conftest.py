"""Shared offline fixtures: small seeded panels, no network access."""

import sys
from collections.abc import Iterator
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import polars as pl  # noqa: E402
import pytest  # noqa: E402
from demand_forecasting.config import DemandSettings, ForecastConfig  # noqa: E402


@pytest.fixture
def config() -> ForecastConfig:
    """Fast configuration: short history, small hierarchy, fewer folds."""
    return ForecastConfig(
        n_days=160, n_stores=2, n_products=2, lags=[1, 7], n_splits=3, gap=3, min_train_size=30
    )


@pytest.fixture
def settings(tmp_path: Path) -> DemandSettings:
    """Settings pointed at a temp data/reports dir."""
    return DemandSettings(
        data_dir=tmp_path / "data", reports_dir=tmp_path / "reports", min_newest_date="2023-01-01"
    )


@pytest.fixture
def panel(config: ForecastConfig) -> pl.DataFrame:
    """Seeded two-store two-product daily panel."""
    from demand_forecasting.data import build_panel

    return build_panel(DemandSettings(), config)


@pytest.fixture
def features(panel: pl.DataFrame, config: ForecastConfig) -> pl.DataFrame:
    """Feature frame built from the small panel."""
    from demand_forecasting.features import build_features

    return build_features(panel, config)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail loudly if any test touches the network."""
    import socket

    def _blocked(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network access is not allowed in tests")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    yield
