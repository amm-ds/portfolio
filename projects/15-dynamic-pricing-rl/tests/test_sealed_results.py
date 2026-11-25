"""E2-8 consumed-artifact integrity checks; never rerun sealed evaluation."""

import json
from pathlib import Path
from typing import Any

from dynamic_pricing.calibrate import load_params
from dynamic_pricing.ledger import canonical_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> Any:
    return json.loads((PROJECT_ROOT / "reports" / name).read_text())


def test_exactly_one_ordered_seal_read_per_frozen_set() -> None:
    rows = _load("sealed_access.json")
    params = load_params(PROJECT_ROOT / "params.yaml")
    names = ["test", "stress_mean_m1_5", "stress_mean_m3_5"]
    assert [row["split"] for row in rows] == names
    assert all(row["purpose"] == "seal_read" and row["step"] == "E2-8" for row in rows)
    for row in rows:
        expected = params["preregistration"]["evaluation_sets"][row["split"]]["specs_sha256"]
        assert row["sha256"] == expected
        assert row["path"] == "projects/15-dynamic-pricing-rl/data/splits.json"
    assert [row["ts"] for row in rows] == sorted(row["ts"] for row in rows)


def test_sealed_metrics_match_frozen_verdict_rules_and_episode_rows() -> None:
    metrics = _load("metrics.json")
    episodes = _load("test_episodes.json")
    params = load_params(PROJECT_ROOT / "params.yaml")
    preregistration = params["preregistration"]
    assert metrics["preregistration_sha256"] == canonical_sha256(preregistration)
    assert metrics["selected_seed"] == 1
    assert episodes["selection"]["price_trace_indices"] == metrics["price_trace_indices"]
    assert len(episodes["price_traces"]) == 3
    for trace in episodes["price_traces"].values():
        assert set(trace["policies"]) == {"B1", "RL"}
        assert all(len(rows) == 91 for rows in trace["policies"].values())

    for set_name, definition in preregistration["evaluation_sets"].items():
        payload = episodes["sets"][set_name]
        assert len(payload["specs"]) == definition["n"]
        for policy_id, policy in payload["policies"].items():
            assert len(policy["normalised_profit"]) == definition["n"]
            assert len(policy["raw_gross_profit"]) == definition["n"]
            if policy_id != "UB":
                assert policy["violations"] == [0] * definition["n"]

    primary = metrics["primary"]
    rule = preregistration["hypotheses"]["P1"]
    expected_p1 = (
        primary["relative_lift"] >= rule["relative_lift_min"]
        and primary["paired_difference"]["lo"] > rule["paired_difference_ci_lower_exclusive"]
    )
    assert primary["passes"] is expected_p1
    assert metrics["verdicts"]["P1"] == ("pass" if expected_p1 else "fail")
    expected_p2 = all(
        value == preregistration["hypotheses"]["P2"]["violations_exactly"]
        for value in metrics["constraint_gate"]["violations_by_policy"].values()
    )
    assert metrics["constraint_gate"]["passes"] is expected_p2
    assert metrics["verdicts"]["P2"] == ("pass" if expected_p2 else "fail")


def test_episode_evidence_stays_within_git_size_budget() -> None:
    path = PROJECT_ROOT / "reports" / "test_episodes.json"
    assert path.stat().st_size <= 2 * 1024 * 1024
