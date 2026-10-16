"""Config + data layer: schema mapping, DQ gates, local-path ingest."""

from pathlib import Path

import polars as pl
import pytest
from uplift_experimentation.config import UpliftConfig
from uplift_experimentation.data import load_experiment_frame, segment_summary


def test_config_defaults_match_params() -> None:
    cfg = UpliftConfig()
    assert cfg.treatment_segment == "Mens E-Mail"
    assert cfg.control_segment == "No E-Mail"
    assert cfg.policy_budget == 0.25
    assert cfg.alpha == 0.05 and cfg.power == 0.8
    assert (
        cfg.hillstrom_sha256 == "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
    )


def test_config_rejects_unsorted_budgets() -> None:
    with pytest.raises(ValueError, match="sorted"):
        UpliftConfig(budget_fractions=[0.5, 0.1])


def test_load_experiment_frame_from_local_path(
    tmp_path: Path, hillstrom_like: pl.DataFrame
) -> None:
    raw = tmp_path / "hillstrom.csv"
    hillstrom_like.write_csv(raw)
    cfg = UpliftConfig(hillstrom_source=str(raw), hillstrom_sha256="")
    df = load_experiment_frame(cfg, raw_path=raw)
    # 12 rows, 8 in the two Mens/No-E-Mail arms (4 Womens E-Mail rows dropped).
    assert df.height == 8
    assert set(df["segment"].unique().to_list()) == {"Mens E-Mail", "No E-Mail"}
    assert "treatment" in df.columns and "log_history" in df.columns


def test_load_experiment_frame_rejects_bad_segments(
    tmp_path: Path, hillstrom_like: pl.DataFrame
) -> None:
    raw = tmp_path / "hillstrom.csv"
    hillstrom_like.with_columns(pl.lit("Telemarketing").alias("segment")).write_csv(raw)
    cfg = UpliftConfig(hillstrom_source=str(raw), hillstrom_sha256="")
    with pytest.raises(ValueError, match="segment"):
        load_experiment_frame(cfg, raw_path=raw)


def test_fetch_hillstrom_checksum_mismatch(tmp_path: Path) -> None:
    from uplift_experimentation.data import fetch_hillstrom

    raw = tmp_path / "hillstrom.csv"
    raw.write_text("recency,history_segment\n1,x\n")
    cfg = UpliftConfig(
        hillstrom_source=str(raw),
        hillstrom_sha256="a" * 64,
        data_dir=tmp_path / "data",
    )
    with pytest.raises(ValueError, match="checksum"):
        fetch_hillstrom(cfg)


def test_segment_summary_three_arms(hillstrom_like: pl.DataFrame) -> None:
    summary = segment_summary(hillstrom_like)
    assert summary.height == 3
    by_segment = {row["segment"]: row for row in summary.to_dicts()}
    assert by_segment["Mens E-Mail"]["n"] == 4
    assert by_segment["Womens E-Mail"]["conversion_rate"] == 0.0
    assert by_segment["No E-Mail"]["conversion_rate"] == 1.0
    assert by_segment["No E-Mail"]["visit_rate"] == 0.5
