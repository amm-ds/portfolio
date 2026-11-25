"""E2-8 gate computation, sealed-read guard, and trace capture tests."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dynamic_pricing.baselines import make_baseline, run_baseline
from dynamic_pricing.calibrate import SeriesCalibration, load_params
from dynamic_pricing.env import EpisodeSpec
from dynamic_pricing.evaluate import TracePricingEnv, _compute_gates, _existing_access

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _payload(rl: list[float], comparator: list[float]) -> dict[str, Any]:
    policies = {
        policy_id: {
            "normalised_profit": [0.4, 0.5],
            "raw_gross_profit": [10.0, 20.0],
            "violations": [0, 0],
        }
        for policy_id in ("B0", "B1", "B2", "B3")
    }
    policies["B1"]["normalised_profit"] = comparator
    policies["RL"] = {
        "normalised_profit": rl,
        "raw_gross_profit": [12.0, 22.0],
        "violations": [0, 0],
    }
    policies["UB"] = {"normalised_profit": [0.8, 0.9], "raw_gross_profit": [30.0, 40.0]}
    return {
        "specs": [
            {"series_id": "series", "epsilon": -2.5, "rho": 0.7, "seed": 1},
            {"series_id": "series", "epsilon": -2.5, "rho": 1.0, "seed": 2},
        ],
        "policies": policies,
    }


def test_p1_and_p2_verdicts_come_from_frozen_rules() -> None:
    preregistration = load_params(PROJECT_ROOT / "params.yaml")["preregistration"]
    primary, constraints, verdicts = _compute_gates(
        _payload([0.53, 0.55], [0.50, 0.50]), preregistration
    )
    assert primary["comparator"] == "B1"
    assert primary["relative_lift"] == pytest.approx(0.08)
    assert primary["paired_difference"]["point"] == pytest.approx(0.04)
    assert primary["paired_difference"]["n_resamples"] == 2000
    assert primary["paired_difference"]["seed"] == 42
    assert primary["passes"]
    assert constraints["violations_by_policy"] == {
        "B0": 0,
        "B1": 0,
        "B2": 0,
        "B3": 0,
        "RL": 0,
    }
    assert constraints["passes"]
    assert verdicts == {"P1": "pass", "P2": "pass", "P3": "context_only"}


def test_p1_fails_when_relative_lift_is_below_threshold() -> None:
    preregistration = load_params(PROJECT_ROOT / "params.yaml")["preregistration"]
    primary, _, verdicts = _compute_gates(_payload([0.51, 0.53], [0.50, 0.50]), preregistration)
    assert primary["relative_lift"] == pytest.approx(0.04)
    assert primary["paired_difference"]["lo"] > 0.0
    assert primary["passes"]
    primary, _, verdicts = _compute_gates(_payload([0.49, 0.51], [0.50, 0.50]), preregistration)
    assert primary["relative_lift"] < 0.01
    assert not primary["passes"]
    assert verdicts["P1"] == "fail"


def test_p2_fails_on_any_executable_policy_violation() -> None:
    preregistration = load_params(PROJECT_ROOT / "params.yaml")["preregistration"]
    payload = _payload([0.53, 0.55], [0.50, 0.50])
    payload["policies"]["B2"]["violations"] = [0, 1]
    _, constraints, verdicts = _compute_gates(payload, preregistration)
    assert not constraints["passes"]
    assert constraints["violations_by_policy"]["B2"] == 1
    assert verdicts["P2"] == "fail"


def test_any_prior_seal_read_hard_fails(tmp_path: Path) -> None:
    path = tmp_path / "sealed_access.json"
    path.write_text(json.dumps([{"purpose": "seal_read", "split": "test"}]))
    with pytest.raises(RuntimeError, match="permanently consumed"):
        _existing_access(path)


def test_trace_capture_uses_development_episode_only() -> None:
    calibration = SeriesCalibration(
        series_id="series",
        item_id="item",
        base=5.0,
        dow=(1.0,) * 7,
        k=100.0,
        p_ref=2.0,
    )
    env = TracePricingEnv({"series": calibration})
    spec = EpisodeSpec("series", -2.5, 0.7, 42)
    result = run_baseline(env, spec, make_baseline("B0"))
    assert result.violations == 0
    assert len(env.trace) == 91
    assert [row["day"] for row in env.trace] == list(range(91))
    assert np.allclose([row["multiplier"] for row in env.trace], 1.0)
    assert all(row["inventory"] >= 0 for row in env.trace)
