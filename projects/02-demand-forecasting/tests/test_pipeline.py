"""Data preparation: DQ gates, dataset contract, end-to-end evaluate persistence."""

import json
from pathlib import Path

import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.data import build_panel, dataset_contract, prepare, validate_panel
from demand_forecasting.evaluate import evaluate
from demand_forecasting.features import build_features
from demand_forecasting.model import fit_all, load_models, save_models
from portfolio_core.dq import DQGateError


def test_prepare_persists_panel_and_contract(
    settings: DemandSettings, config: ForecastConfig
) -> None:
    path = prepare(settings, config)
    assert path.exists()
    panel = pl.read_parquet(path)
    assert panel.height == config.n_days * config.n_stores * config.n_products
    contract = json.loads((settings.data_dir / "dataset.json").read_text())
    assert contract["n_rows"] == panel.height
    assert contract["source"].startswith("synthetic://")
    assert len(contract["checksum_sha256"]) == 64


def test_dataset_contract_is_deterministic(
    settings: DemandSettings, config: ForecastConfig
) -> None:
    a = dataset_contract(build_panel(settings, config), settings)
    b = dataset_contract(build_panel(settings, config), settings)
    assert a.checksum_sha256 == b.checksum_sha256


def test_dq_gate_fails_on_nulls(
    settings: DemandSettings, config: ForecastConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel = build_panel(settings, config).with_columns(
        pl.when(pl.arange(0, pl.len()) == 0).then(None).otherwise(pl.col("units")).alias("units")
    )
    with pytest.raises(DQGateError):
        validate_panel(panel, settings)


def test_evaluate_writes_report_and_figures(
    settings: DemandSettings, config: ForecastConfig
) -> None:
    prepare(settings, config)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    from demand_forecasting.features import save_features

    save_features(frame, settings)
    result = evaluate(settings, config)

    metrics = json.loads((settings.reports_dir / "metrics.json").read_text())
    assert set(metrics) == {"naive_mean", "naive_last", "ridge", "hgb"}
    for run in result.runs:
        for m in run.metrics:
            assert metrics[run.name][m.name] == pytest.approx(m.value)

    assert (settings.reports_dir / "report.html").exists()
    for name in (
        "eda_series_overview",
        "eda_units_distribution",
        "forecast_vs_actual",
        "metrics_bars",
        "fold_stability",
    ):
        assert (settings.reports_dir / "figures" / f"{name}.html").exists()
        assert (settings.reports_dir / "figures" / f"{name}.json").exists()


def test_model_persistence_roundtrip(
    features: pl.DataFrame, config: ForecastConfig, tmp_path: Path
) -> None:
    from demand_forecasting.model import model_specs, to_xy

    models = fit_all(features, config)
    path = save_models(models, tmp_path / "models.pkl")
    loaded = load_models(path)
    assert set(loaded) == {"naive_mean", "naive_last", "ridge", "hgb"}
    spec = next(s for s in model_specs() if s.name == "ridge")
    x, _, _, _ = to_xy(features, config, spec)
    pred = loaded["ridge"].predict(x)
    assert pred.shape == (features.height,)
