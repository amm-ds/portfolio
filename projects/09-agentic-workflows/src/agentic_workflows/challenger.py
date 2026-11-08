"""Correctness-first incumbent/Kimi comparison for the workflow suites."""

import json
from pathlib import Path
from typing import Any, cast

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme, save_json

from agentic_workflows.config import EvalConfig, get_settings


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _figure(incumbent: dict[str, Any], challenger: dict[str, Any]) -> go.Figure:
    before = incumbent["agentic_suite"]
    after = challenger["agentic_suite"]
    before_h = incumbent["detail"]["heldout"]
    after_h = challenger["detail"]["heldout"]
    labels = ["tuning answers", "tuning tools", "held-out answers", "held-out tools", "refusals"]
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=("correctness", "mean latency (s)", "estimated cost / task (USD)"),
    )
    fig.add_bar(
        x=labels,
        y=[
            before["success_rate"],
            before["tool_selection_accuracy"],
            before_h["answer_success"],
            before_h["tool_selection"],
            before_h["should_fail_pass_rate"],
        ],
        name="incumbent",
        row=1,
        col=1,
    )
    fig.add_bar(
        x=labels,
        y=[
            after["success_rate"],
            after["tool_selection_accuracy"],
            after_h["answer_success"],
            after_h["tool_selection"],
            after_h["should_fail_pass_rate"],
        ],
        name="Kimi",
        row=1,
        col=1,
    )
    for label, key in [("incumbent", before), ("Kimi", after)]:
        fig.add_bar(x=[label], y=[key["avg_latency_s"]], name=label, row=1, col=2, showlegend=False)
        fig.add_bar(
            x=[label], y=[key["est_cost_usd_per_task"]], name=label, row=1, col=3, showlegend=False
        )
    fig.update_layout(
        title="Workflow model selection — correctness before efficiency", yaxis_range=[0, 1.05]
    )
    add_takeaway(
        fig,
        "same tasks and deterministic graders; Kimi is selected only when "
        "correctness holds and latency or cost improves",
    )
    return apply_theme(fig)


def compare_challenger(config: EvalConfig, challenger_dir: Path) -> dict[str, Any]:
    """Write the comparison, selecting Kimi only on a correctness-safe Pareto gain."""
    incumbent = _load(config.reports_dir / "metrics.json")
    challenger = _load(challenger_dir / "metrics.json")
    before = incumbent["agentic_suite"]
    after = challenger["agentic_suite"]
    before_h = incumbent["detail"]["heldout"]
    after_h = challenger["detail"]["heldout"]
    correctness_holds = (
        after["success_rate"] >= 1.0
        and after["tool_selection_accuracy"] >= 1.0
        and after_h["answer_success"] >= before_h["answer_success"]
        and after_h["tool_selection"] >= before_h["tool_selection"]
        and after_h["should_fail_pass_rate"] >= before_h["should_fail_pass_rate"]
        and after_h["step_budget"] >= before_h["step_budget"]
    )
    efficiency_improves = (
        after["avg_latency_s"] < before["avg_latency_s"]
        or after["est_cost_usd_per_task"] < before["est_cost_usd_per_task"]
    )
    selected = "kimi" if correctness_holds and efficiency_improves else "incumbent"
    result = {
        "selected": selected,
        "challenger_model": get_settings().llm_model or "configured-hosted-model",
        "correctness_holds": correctness_holds,
        "efficiency_improves": efficiency_improves,
        "incumbent": {"suite": before, "heldout": before_h},
        "challenger": {"suite": after, "heldout": after_h},
        "deltas": {
            "avg_latency_s": after["avg_latency_s"] - before["avg_latency_s"],
            "est_cost_usd_per_task": after["est_cost_usd_per_task"]
            - before["est_cost_usd_per_task"],
            "heldout_answer_success": after_h["answer_success"] - before_h["answer_success"],
            "heldout_tool_selection": after_h["tool_selection"] - before_h["tool_selection"],
            "should_fail_pass_rate": after_h["should_fail_pass_rate"]
            - before_h["should_fail_pass_rate"],
        },
    }
    output = config.reports_dir / "kimi_comparison.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    save_json(
        _figure(incumbent, challenger),
        config.reports_dir / "figures" / "kimi_workflow_comparison.json",
    )
    return result
