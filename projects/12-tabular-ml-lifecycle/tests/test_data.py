"""Prepare/contract tests: schema, sha256 gate, DQ gates, UCI zip loading."""

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from portfolio_core.dq import DQGateError
from portfolio_core.schemas import DatasetContract
from tabular_ml_lifecycle.data import (
    TARGET_COL,
    TIMESTAMP_COL,
    UCI_COLUMNS,
    load_uci_frame,
    run_dq_gates,
    split_windows,
)

SHA = "b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401"


def _fixture_zip(path: Path, n_rows: int = 96) -> Path:
    """Tiny valid hour.csv inside a zip, for loader tests without the network."""
    rows = []
    for i in range(n_rows):
        rows.append(
            {
                "instant": i + 1,
                "dteday": f"2011-01-{1 + i // 24:02d}",
                "season": 1,
                "yr": 0,
                "mnth": 1,
                "hr": i % 24,
                "holiday": 0,
                "weekday": (i // 24) % 7,
                "workingday": 1,
                "weathersit": 1,
                "temp": 0.3,
                "atemp": 0.32,
                "hum": 0.6,
                "windspeed": 0.1,
                "casual": 10,
                "registered": 50,
                "cnt": 60,
            }
        )
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("hour.csv", buf.getvalue())
    return path


def test_synthetic_frame_passes_dq(small_frame: pd.DataFrame) -> None:
    report = run_dq_gates(small_frame)
    assert report.passed, report.to_markdown()
    assert report.n_rows == len(small_frame)


def test_contract_schema_roundtrips(contract: DatasetContract) -> None:
    dumped = contract.model_dump_json()
    assert DatasetContract.model_validate_json(dumped) == contract
    assert contract.n_rows == 140 * 24
    assert contract.checksum_sha256 == contract.checksum_sha256.lower()


def test_split_windows_are_ordered_and_disjoint(small_frame: pd.DataFrame) -> None:
    windows = split_windows(len(small_frame), val_weeks=2, test_weeks=2)
    assert windows.train.stop <= windows.val.start < windows.val.stop <= windows.test.start
    assert windows.n_val == windows.n_test == 2 * 24 * 7
    assert windows.n_train + windows.n_val + windows.n_test == len(small_frame)
    assert windows.test.start == len(small_frame) - windows.n_test


def test_split_windows_reject_short_series() -> None:
    with pytest.raises(ValueError, match="too short"):
        split_windows(24 * 20, val_weeks=2, test_weeks=2)


def test_uci_loader_maps_schema(tmp_path: Path) -> None:
    zip_path = _fixture_zip(tmp_path / "bike.zip")
    # checksum gate is bypassed by pointing at the raw file with its own hash
    from portfolio_core.io import sha256_of

    df = load_uci_frame(str(zip_path), sha256_of(zip_path))
    assert list(df.columns) == [
        TIMESTAMP_COL,
        "season",
        "month",
        "hour",
        "weekday",
        "weathersit",
        "holiday",
        "workingday",
        "temp",
        "atemp",
        "hum",
        "windspeed",
        TARGET_COL,
    ]
    assert set(UCI_COLUMNS.values()) == set(df.columns)
    assert not df[TIMESTAMP_COL].duplicated().any()
    assert run_dq_gates(df).passed


def test_uci_loader_rejects_corrupted_zip(tmp_path: Path) -> None:
    """The sha256 gate refuses a file whose bytes drifted."""
    zip_path = tmp_path / "bike.zip"
    zip_path.write_bytes(b"not a zip at all")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_uci_frame(str(zip_path), SHA)
    # a structurally valid zip with a wrong pin is also refused
    valid = _fixture_zip(tmp_path / "other.zip")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_uci_frame(str(valid), SHA)


def test_uci_loader_rejects_tampered_zip_content(tmp_path: Path) -> None:
    """Flip bytes inside the zip: the pin must catch content drift too."""
    zip_path = _fixture_zip(tmp_path / "bike.zip")
    data = bytearray(zip_path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    tampered = tmp_path / "tampered.zip"
    tampered.write_bytes(bytes(data))
    from portfolio_core.io import sha256_of

    assert sha256_of(tampered) != sha256_of(zip_path)
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_uci_frame(str(tampered), sha256_of(zip_path))


def test_dq_gate_catches_duplicates(small_frame: pd.DataFrame) -> None:
    duped = pd.concat([small_frame, small_frame.iloc[[10]]], ignore_index=True)
    with pytest.raises(DQGateError):
        run_dq_gates(duped)


def test_dq_gate_catches_out_of_range(small_frame: pd.DataFrame) -> None:
    broken = small_frame.copy()
    broken.loc[0, "hour"] = 25
    with pytest.raises(DQGateError):
        run_dq_gates(broken)


def test_dq_gate_catches_excessive_gaps(tmp_path: Path) -> None:
    """Gaps beyond the 2% budget fail; the real series' ~1% passes by design."""
    rows = []
    base = pd.Timestamp("2011-01-01")
    for i in range(240):
        if i % 4 == 0:  # 25% missing — far over the 2% / 24-step budget
            continue
        rows.append(base + pd.to_timedelta(i + i // 4, unit="h"))
    df = pd.DataFrame(
        {
            TIMESTAMP_COL: rows,
            "season": 1,
            "month": 1,
            "hour": [t.hour for t in rows],
            "weekday": 0,
            "weathersit": 1,
            "holiday": 0,
            "workingday": 1,
            "temp": 0.3,
            "atemp": 0.3,
            "hum": 0.5,
            "windspeed": 0.1,
            TARGET_COL: 10,
        }
    )
    with pytest.raises(DQGateError):
        run_dq_gates(df)
