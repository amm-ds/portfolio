"""Committed figure payloads must agree with the numbers in their own traces."""

import json
from pathlib import Path

FIGURES = Path(__file__).parents[1] / "reports" / "figures"


def _load(name: str) -> dict:
    return json.loads((FIGURES / f"{name}.json").read_text())


def test_suite_summary_title_matches_graded_counts() -> None:
    data = _load("suite_summary")["data"]
    counts = {}
    for trace in data:
        for row, label in zip(trace["y"], trace["text"], strict=True):
            if label:
                passed, total = label.split("/")
                counts[(trace["name"], row)] = (int(passed), int(total))
    answers = [v for (_, row), v in counts.items() if row == "answers"]
    assert answers and all(p == t for p, t in answers)
    probes = next(v for (_, row), v in counts.items() if row == "graceful refusals")
    title = _load("suite_summary")["layout"]["title"]["text"]
    assert "Every answer task passes" in title
    assert f"{probes[1] - probes[0]} of {probes[1]} refusal probes failed" in title


def test_cost_latency_title_matches_traces() -> None:
    data = _load("cost_latency_bars")["data"]
    latency = next(t for t in data if t["name"] == "latency")
    budget = next(t for t in data if t["name"] == "latency budget")
    cost = next(t for t in data if t["name"] == "cloud-equivalent cost per task")
    assert max(latency["y"]) < min(budget["y"])
    suite_cost = sum(float(label.lstrip("$")) for label in cost["text"])
    title = _load("cost_latency_bars")["layout"]["title"]["text"]
    assert f"All {len(latency['x'])} practice tasks" in title
    assert f"${suite_cost:.2f} per suite" in title


def test_node_waterfall_title_matches_traces() -> None:
    data = _load("node_waterfall")["data"]
    totals: dict[str, float] = {}
    widest = ("", "", 0.0)
    for trace in data:
        totals[trace["name"]] = sum(trace["x"])
        for task, width in zip(trace["y"], trace["x"], strict=True):
            if width > widest[2]:
                widest = (task, trace["name"], width)
    dominant = max(totals, key=lambda node: totals[node])
    title = _load("node_waterfall")["layout"]["title"]["text"]
    assert title.startswith(f"{dominant.capitalize()} dominates task time")
    assert f"{widest[0]} {widest[1].capitalize()} at {widest[2]:.0f} s" in title


def test_tool_usage_title_matches_zero_out_of_set() -> None:
    """The heatmap holds raw call counts; the in-plan claim is graded by the
    exact-tool-set bar in suite_summary (every call inside the planned set)."""
    heatmap = _load("tool_usage_matrix")["data"]
    assert heatmap[0]["type"] == "heatmap"
    summary = _load("suite_summary")["data"]
    tuning = next(t for t in summary if t["name"].startswith("tuning suite"))
    row = tuning["y"].index("exact tool set")
    passed, total = tuning["text"][row].split("/")
    assert passed == total
    title = _load("tool_usage_matrix")["layout"]["title"]["text"]
    assert "zero out-of-set calls" in title
