"""E2-5 recorded tuning and comparator-lock gate."""

import json
from pathlib import Path

from dynamic_pricing.calibrate import load_params

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_recorded_comparator_is_the_best_validation_baseline() -> None:
    report = json.loads((PROJECT_ROOT / "reports" / "baselines_val.json").read_text())
    assert report["train"]["n_episodes"] == 2000
    assert report["val"]["n_episodes"] == 300
    assert len(report["train"]["b1_grid"]) == 7
    assert len(report["train"]["b2_grid"]) == 16
    policies = report["val"]["policies"]
    expected = max(policies, key=lambda policy: policies[policy]["mean_normalised_profit"])
    assert report["comparator"] == expected
    assert load_params(PROJECT_ROOT / "params.yaml")["comparator"] == expected
    assert all(result["violations"] == 0 for result in policies.values())
