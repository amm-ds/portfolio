"""CLI tests: every command runs end-to-end against tmp-dir artifacts."""

from pathlib import Path

import pytest
from anomaly_detection import cli
from anomaly_detection.config import AnomalyConfig
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def tiny_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AnomalyConfig:
    config = AnomalyConfig(
        n=1_500,
        hpo_trials=4,
        data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
    )
    monkeypatch.setattr(cli, "get_config", lambda: config)
    return config


def test_prepare_command(tiny_config: AnomalyConfig) -> None:
    result = runner.invoke(cli.app, ["prepare"])
    assert result.exit_code == 0, result.output
    assert tiny_config.raw_path.exists()
    assert tiny_config.contract_path.exists()


def test_validate_and_dq_report_commands(tiny_config: AnomalyConfig) -> None:
    assert runner.invoke(cli.app, ["prepare"]).exit_code == 0
    result = runner.invoke(cli.app, ["validate"])
    assert result.exit_code == 0, result.output
    assert tiny_config.dq_report_path.exists()
    result = runner.invoke(cli.app, ["dq-report"])
    assert result.exit_code == 0, result.output
    assert "DQ report" in result.output


def test_validate_command_fails_loudly_on_bad_data(
    tiny_config: AnomalyConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import polars as pl

    assert runner.invoke(cli.app, ["prepare"]).exit_code == 0
    raw = pl.read_parquet(tiny_config.raw_path)
    corrupted = raw.with_columns(
        pl.when(pl.int_range(pl.len()) % 10 == 0).then(None).otherwise(pl.col("cpu")).alias("cpu")
    )
    corrupted.write_parquet(tiny_config.raw_path)
    result = runner.invoke(cli.app, ["validate"])
    assert result.exit_code != 0
    assert tiny_config.dq_report_path.exists()  # report artifact survives the failure


def test_features_and_train_commands(tiny_config: AnomalyConfig) -> None:
    assert runner.invoke(cli.app, ["prepare"]).exit_code == 0
    result = runner.invoke(cli.app, ["features"])
    assert result.exit_code == 0, result.output
    assert tiny_config.features_path.exists()
    result = runner.invoke(cli.app, ["train"])
    assert result.exit_code == 0, result.output
    for name in tiny_config.models:
        assert (tiny_config.models_dir / f"{name}.joblib").exists()


def test_tune_command(tiny_config: AnomalyConfig) -> None:
    assert runner.invoke(cli.app, ["prepare"]).exit_code == 0
    assert runner.invoke(cli.app, ["features"]).exit_code == 0
    assert runner.invoke(cli.app, ["train"]).exit_code == 0
    result = runner.invoke(cli.app, ["tune"])
    assert result.exit_code == 0, result.output
    for name in tiny_config.models:
        assert (tiny_config.tuned_models_dir / f"{name}_tuned.joblib").exists()
        assert (tiny_config.tuned_models_dir / f"{name}_hpo.json").exists()


def test_evaluate_command(tiny_config: AnomalyConfig) -> None:
    assert runner.invoke(cli.app, ["prepare"]).exit_code == 0
    assert runner.invoke(cli.app, ["features"]).exit_code == 0
    assert runner.invoke(cli.app, ["train"]).exit_code == 0
    result = runner.invoke(cli.app, ["evaluate"])
    assert result.exit_code == 0, result.output
    assert "isolation_forest" in result.output
    assert (tiny_config.eval_dir / "metrics.json").exists()
    assert (tiny_config.eval_dir / "report.html").exists()


def test_all_command_runs_full_pipeline(tiny_config: AnomalyConfig) -> None:
    result = runner.invoke(cli.app, ["all"])
    assert result.exit_code == 0, result.output
    assert tiny_config.raw_path.exists()
    assert tiny_config.features_path.exists()
    assert (tiny_config.models_dir / "ocsvm.joblib").exists()
    assert (tiny_config.tuned_models_dir / "isolation_forest_tuned.joblib").exists()
    assert (tiny_config.eval_dir / "metrics.json").exists()
    assert "roc_auc" in result.output


def test_all_command_exposes_dq_failure(
    tiny_config: AnomalyConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pipeline must halt loudly when DQ gates fail — even in `all`."""
    import polars as pl
    from anomaly_detection.data import prepare as data_prepare
    from anomaly_detection.data import save_raw as save_raw

    def corrupt_prepare(config: AnomalyConfig) -> pl.DataFrame:
        df = data_prepare(config)
        corrupted = df.with_columns(
            pl.when(pl.int_range(pl.len()) % 5 == 0)
            .then(None)
            .otherwise(pl.col("latency_ms"))
            .alias("latency_ms")
        )
        save_raw(corrupted, config)
        return corrupted

    monkeypatch.setattr("anomaly_detection.cli.prepare", corrupt_prepare)
    result = runner.invoke(cli.app, ["all"])
    assert result.exit_code != 0
    assert not tiny_config.features_path.exists()
    assert tiny_config.dq_report_path.exists()
