"""Config validation and settings behaviour."""

import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from pydantic import ValidationError


def test_forecast_config_defaults() -> None:
    """Defaults match the project spec exactly."""
    c = ForecastConfig()
    assert c.n_days == 730
    assert c.n_stores == 4
    assert c.n_products == 6
    assert c.lags == [1, 7, 14]
    assert c.n_splits == 4
    assert c.gap == 7
    assert c.max_lag == 14


def test_forecast_config_extra_forbidden() -> None:
    """The platform base model is strict: typos must not be silently accepted."""
    with pytest.raises(ValidationError):
        ForecastConfig(n_days=730, typo_field=1)  # type: ignore[call-arg]


def test_lags_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ForecastConfig(lags=[0, 7])
    with pytest.raises(ValidationError):
        ForecastConfig(lags=[])


def test_lags_sorted_deduplicated() -> None:
    c = ForecastConfig(lags=[14, 1, 7, 7])
    assert c.lags == [1, 7, 14]


def test_n_days_floor() -> None:
    with pytest.raises(ValidationError):
        ForecastConfig(n_days=10)


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED", "7")
    s = DemandSettings()
    assert s.seed == 7


def test_settings_subclass_has_dataset_card() -> None:
    s = DemandSettings()
    assert s.dataset_source.startswith("synthetic://")
    assert s.dataset_name == "retail-hierarchy-synthetic"
