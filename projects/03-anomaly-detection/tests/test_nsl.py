"""NSL-KDD track tests: parsing, schema mapping, transfer probe (offline)."""

from pathlib import Path

import polars as pl
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.nsl import (
    CATEGORICAL_COLUMNS,
    KDD_FEATURE_COLUMNS,
    feature_frame,
    parse_nsl_txt,
    transfer_probe,
)


def _fixture_txt(path: Path, rows: list[tuple[str, ...]]) -> Path:
    """Write a tiny KDD-shaped CSV (43 columns, no header)."""
    lines = [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def _row(label: str, duration: int = 0, src_bytes: int = 100) -> tuple[str, ...]:
    values = [str(duration), "tcp", "http", "SF", str(src_bytes), "0"]
    values += ["0"] * (41 - len(values))
    return (*values, label, "20")


def test_parse_nsl_txt_schema(tmp_path: Path) -> None:
    path = _fixture_txt(tmp_path / "KDDTrain+.txt", [_row("normal"), _row("neptune")])
    df = parse_nsl_txt(path)
    assert df.width == 43
    assert df.columns[-2:] == ["label", "difficulty"]
    assert df["protocol_type"].to_list() == ["tcp", "tcp"]
    assert set(CATEGORICAL_COLUMNS) <= set(KDD_FEATURE_COLUMNS)


def test_parse_nsl_txt_rejects_bad_width(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_text("1,2,3\n")
    with pytest.raises((pl.exceptions.ComputeError, pl.exceptions.SchemaError, ValueError)):
        parse_nsl_txt(path)


def test_feature_frame_maps_to_numeric(tmp_path: Path) -> None:
    rows = [_row("normal"), _row("neptune", duration=5, src_bytes=999)]
    df = parse_nsl_txt(_fixture_txt(tmp_path / "kdd_fixture.txt", rows))
    mapped = feature_frame(df)
    assert mapped.width == 41  # 43 - label - difficulty
    assert all(t.is_numeric() for t in mapped.dtypes)
    assert "protocol_type" in mapped.columns  # factorized categorical kept


def test_transfer_probe_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import anomaly_detection.nsl as nsl_module

    config = AnomalyConfig(data_dir=str(tmp_path / "d"), reports_dir=str(tmp_path / "r"))
    train_rows = [_row("normal", duration=0) for _ in range(40)] + [
        _row("neptune", duration=50, src_bytes=9000) for _ in range(40)
    ]
    test_rows = [_row("normal", duration=1) for _ in range(15)] + [
        _row("neptune", duration=49, src_bytes=8500) for _ in range(15)
    ]
    train = parse_nsl_txt(_fixture_txt(tmp_path / "train.txt", train_rows))
    test = parse_nsl_txt(_fixture_txt(tmp_path / "test.txt", test_rows))
    contract = nsl_module.DatasetContract(
        name="nsl-kdd",
        source="fixture://nsl",
        license="fixture",
        snapshot_date=config.snapshot_date,
        checksum_sha256="a" * 64,
        n_rows=train.height,
    )
    monkeypatch.setattr(nsl_module, "load_nsl", lambda cfg: (train, test, contract))

    result = transfer_probe(config)
    assert result["n_train"] == 80 and result["n_test"] == 30
    assert result["n_features"] == 41
    assert result["test_anomaly_rate"] == pytest.approx(0.5)
    assert 0.0 <= result["roc_auc"] <= 1.0
    assert len(result["caveats"]) >= 3
