"""Client CRM extract onboarding (prepare --input) tests."""

import json
from pathlib import Path

import polars as pl
import pytest
from churn_pipeline.cli import prepare_core
from churn_pipeline.config import ChurnConfig


def _client_csv(tmp_path: Path, with_churned: bool = True) -> Path:
    rows = {
        "age": [30.0, 41.0, 55.0, 62.0, 35.0] * 4 + [None, 47.0, 51.0, 44.0],
        "tenure_months": [2.0, 14.0, 30.0, 6.0, 48.0] * 4 + [9.0, 22.0, 17.0, 3.0],
        "monthly_charges": [45.0, 70.0, 95.0, 60.0, 120.0] * 4 + [66.0, 88.0, 54.0, 99.0],
        "support_calls": [0.0, 1.0, 3.0, 2.0, 1.0] * 4 + [2.0, None, 0.0, 1.0],
        "contract": ["month-to-month", "one-year", "two-year", "month-to-month", "one-year"] * 4
        + ["two-year", "one-year", "month-to-month", "two-year"],
    }
    if with_churned:
        rows["churned"] = [1, 0, 0, 1, 0] * 4 + [0, 1, 0, 0]
    path = tmp_path / "client_extract.csv"
    pl.DataFrame(rows).write_csv(path)
    return path


def test_prepare_ingests_labeled_client_extract(small_cfg: ChurnConfig, tmp_path: Path) -> None:
    csv = _client_csv(tmp_path)
    prepare_core(small_cfg, input_csv=csv)

    df = pl.read_parquet(small_cfg.data_dir / "churn.parquet")
    assert df.height == 24
    contract = json.loads((small_cfg.data_dir / "dataset_contract.json").read_text())
    assert contract["source"] == "client://client_extract.csv"
    assert contract["license"] == "LicenseRef-Client-Contract"
    assert (small_cfg.reports_dir / "dq_report.md").exists()
    assert (small_cfg.reports_dir / "figures" / "eda_churn_profile.json").exists()


def test_prepare_ingests_unlabeled_extract_and_skips_eda(
    small_cfg: ChurnConfig, tmp_path: Path
) -> None:
    csv = _client_csv(tmp_path, with_churned=False)
    prepare_core(small_cfg, input_csv=csv)

    df = pl.read_parquet(small_cfg.data_dir / "churn.parquet")
    assert "churned" not in df.columns
    assert not (small_cfg.reports_dir / "figures" / "eda_churn_profile.json").exists()


def test_prepare_rejects_extract_with_missing_columns(
    small_cfg: ChurnConfig, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.csv"
    pl.DataFrame({"age": [1.0], "contract": ["one-year"]}).write_csv(bad)
    with pytest.raises(ValueError, match="missing required columns"):
        prepare_core(small_cfg, input_csv=bad)
