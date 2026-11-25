"""E2-2 calibration integrity gates."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from dynamic_pricing.calibrate import load_m5, load_params, verify_sources

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]


def _params() -> dict[str, Any]:
    return load_params(PROJECT_ROOT / "params.yaml")


def _splits() -> dict[str, Any]:
    value = json.loads((PROJECT_ROOT / "data" / "splits.json").read_text())
    assert isinstance(value, dict)
    return value


def test_item_splits_are_disjoint_and_exactly_sized() -> None:
    item_ids = _splits()["item_ids"]
    assert {split: len(item_ids[split]) for split in ("train", "val", "test")} == {
        "train": 140,
        "val": 30,
        "test": 30,
    }
    all_items = [item for split in ("train", "val", "test") for item in item_ids[split]]
    assert len(all_items) == len(set(all_items))


def test_loader_never_uses_dates_after_calibration_cutoff() -> None:
    params = _params()
    y, x, _ = load_m5(params, REPO_ROOT)
    cutoff = date(2016, 4, 24)
    start = date(2011, 1, 29)
    assert y["ds"].max() == cutoff
    assert x["ds"].max() == cutoff
    assert y["ds"].min() >= start
    assert x["ds"].min() >= start


def test_source_sha_mismatch_raises_before_read() -> None:
    params = _params()
    params["calibration"]["source_files"]["Y"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_sources(params, REPO_ROOT)


def test_all_600_series_have_weekday_profiles_summing_to_seven() -> None:
    rows = json.loads((PROJECT_ROOT / "data" / "calibration.json").read_text())
    assert len(rows) == 600
    for row in rows:
        assert len(row["dow"]) == 7
        assert sum(row["dow"]) == pytest.approx(7.0, abs=1e-6)
        assert row["base"] > 0
        assert 0.5 <= row["k"] <= 100.0
        assert row["p_ref"] > 0


def test_source_hashes_still_match() -> None:
    verify_sources(_params(), REPO_ROOT)
