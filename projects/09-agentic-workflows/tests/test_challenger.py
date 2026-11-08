"""Kimi selection requires held-out correctness plus an efficiency gain."""

import json
from pathlib import Path

from agentic_workflows.challenger import compare_challenger
from agentic_workflows.config import EvalConfig


def _write(path: Path, *, latency: float, cost: float, refusal: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agentic_suite": {
            "success_rate": 1.0,
            "tool_selection_accuracy": 1.0,
            "avg_latency_s": latency,
            "est_cost_usd_per_task": cost,
        },
        "detail": {
            "heldout": {
                "answer_success": 1.0,
                "tool_selection": 1.0,
                "step_budget": 1.0,
                "should_fail_pass_rate": refusal,
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_selects_kimi_when_correctness_holds_and_latency_improves(tmp_path: Path) -> None:
    config = EvalConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write(config.reports_dir / "metrics.json", latency=20.0, cost=0.01, refusal=0.8)
    _write(challenger_dir / "metrics.json", latency=10.0, cost=0.01, refusal=0.8)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "kimi"
    assert result["correctness_holds"] is True
    assert result["efficiency_improves"] is True
    assert (config.reports_dir / "figures" / "kimi_workflow_comparison.json").is_file()


def test_retains_incumbent_when_efficiency_does_not_improve(tmp_path: Path) -> None:
    config = EvalConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write(config.reports_dir / "metrics.json", latency=20.0, cost=0.01, refusal=0.8)
    _write(challenger_dir / "metrics.json", latency=25.0, cost=0.02, refusal=0.8)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "incumbent"
    assert result["efficiency_improves"] is False


def test_retains_incumbent_on_refusal_regression(tmp_path: Path) -> None:
    config = EvalConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write(config.reports_dir / "metrics.json", latency=20.0, cost=0.01, refusal=0.8)
    _write(challenger_dir / "metrics.json", latency=10.0, cost=0.005, refusal=0.5)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "incumbent"
    assert result["correctness_holds"] is False
