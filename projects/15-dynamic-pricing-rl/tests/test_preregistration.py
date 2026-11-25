"""E2-6 frozen protocol and ledger-order integrity gates."""

import json
from pathlib import Path
from typing import Any

from dynamic_pricing.calibrate import load_params
from dynamic_pricing.ledger import canonical_sha256, file_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _splits() -> dict[str, Any]:
    value = json.loads((PROJECT_ROOT / "data" / "splits.json").read_text())
    assert isinstance(value, dict)
    return value


def test_sealed_spec_counts_balance_and_seed_streams() -> None:
    sealed = _splits()["sealed_evaluation"]
    assert {name: len(specs) for name, specs in sealed.items()} == {
        "test": 1000,
        "stress_mean_m1_5": 500,
        "stress_mean_m3_5": 500,
    }
    for name, stream in (("test", 2), ("stress_mean_m1_5", 3), ("stress_mean_m3_5", 4)):
        specs = sealed[name]
        assert specs[0]["seed"] == stream * 1_000_000
        assert specs[-1]["seed"] == stream * 1_000_000 + len(specs) - 1
        counts = {rho: sum(spec["rho"] == rho for spec in specs) for rho in (0.7, 1.0, 1.3)}
        assert max(counts.values()) - min(counts.values()) <= 1
        assert all(-5.0 <= spec["epsilon"] <= -0.8 for spec in specs)


def test_preregistration_hash_and_spec_hashes_match_ledger() -> None:
    params = load_params(PROJECT_ROOT / "params.yaml")
    block = params["preregistration"]
    assert block["comparator"] == params["comparator"] == "B1"
    assert block["hypotheses"]["P1"]["relative_lift_min"] == 0.01
    assert block["hypotheses"]["P2"]["violations_exactly"] == 0
    assert block["paired_bootstrap"] == {
        "unit": "episode",
        "n_resamples": 2000,
        "seed": 42,
        "confidence": 0.95,
    }
    sealed = _splits()["sealed_evaluation"]
    for name, definition in block["evaluation_sets"].items():
        assert definition["specs_sha256"] == canonical_sha256(sealed[name])
    ledger = json.loads((PROJECT_ROOT / "reports" / "experiment_log.json").read_text())
    row = next(row for row in ledger if row["step"] == "E2-6")
    assert row["headline"]["preregistration_sha256"] == canonical_sha256(block)
    assert row["set_sha256"] == file_sha256(PROJECT_ROOT / "data" / "splits.json")
    assert row["request_hosts"] == []


def test_preregistration_ledger_precedes_training_and_evaluation() -> None:
    ledger = json.loads((PROJECT_ROOT / "reports" / "experiment_log.json").read_text())
    preregistration_index = next(index for index, row in enumerate(ledger) if row["step"] == "E2-6")
    later_indices = [
        index for index, row in enumerate(ledger) if row["step"].startswith(("E2-7", "E2-8"))
    ]
    assert later_indices
    assert all(preregistration_index < index for index in later_indices)
    assert all(ledger[index]["request_hosts"] == [] for index in later_indices)
