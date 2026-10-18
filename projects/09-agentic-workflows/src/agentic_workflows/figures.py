"""Story figures for the evaluation report (plotly, dark theme).

Four builders — the suite summary, the tool-usage matrix, the node
waterfall, and cost/latency bars — plus :func:`suite_figures`, the bundle
the report builder writes as ``.html`` + ``.json`` pairs. All figures are
deterministic renderings of the graded report; ids are stable (ADR-0005:
interactive figures are canonical). The workflow graph itself is a mermaid
diagram in the story/docs, not a plotly figure.
"""

from __future__ import annotations

import statistics
from typing import Any

import plotly.graph_objects as go
from portfolio_core.plotting import apply_theme
from pydantic_evals.reporting import EvaluationReport

from agentic_workflows.config import EvalConfig
from agentic_workflows.schemas import EvalTask, TaskRunRecord

#: Canonical column order of the tool-usage matrix figure.
SUITE_TOOLS: tuple[str, ...] = (
    "search_handbook",
    "search_documents",
    "calculator",
    "unit_convert",
    "note_store",
)


def _takeaway_title(fig: go.Figure, headline: str, takeaway: str) -> None:
    """Two-line title: headline plus a dim takeaway line.

    Used instead of ``add_takeaway`` here: the plotly title anchors a fixed
    distance above the plot area, so a separate ``y > 1`` takeaway annotation
    lands on top of it; a ``<br>``-joined span lays out deterministically.
    """
    fig.update_layout(
        title={
            "text": (f"{headline}<br><span style='font-size:13px;color:#cbd5e1'>{takeaway}</span>"),
            "font": {"size": 16},
        },
        margin={"t": 100, "r": 30, "b": 50},
    )


def _score(
    report: EvaluationReport[EvalTask, TaskRunRecord, None], case_name: str, evaluator: str
) -> float:
    case = next((c for c in report.cases if c.name == case_name), None)
    if case is None:
        return 0.0
    # Scalar evaluator outputs land in `assertions`; `scores` holds structured metrics.
    result = case.assertions.get(evaluator) or case.scores.get(evaluator)
    if result is None:
        return 0.0
    value = result.value
    return float(value) if isinstance(value, int | float) else 0.0


def _fig_suite_summary(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
    config: EvalConfig | None,
) -> go.Figure:
    """Outcomes by split — the whole verification story in one chart.

    Grouped horizontal bars over the three graded splits: the tuning suite
    (all four graders), the held-out answer tasks (answers + exact tool
    set), and the should-fail probes (graceful refusals). Held-out counts
    are graded offline from ``data/heldout_records.json`` when present;
    when the held-out artifacts are absent (e.g. a bare synthetic report
    in tests) those bars are simply omitted. The title carries the takeaway.
    """
    entries: list[tuple[str, str, int, int]] = []

    def _add(split: str, row: str, passed: int, total: int) -> None:
        entries.append((split, row, passed, total))

    for grader, row in (
        ("AnswerSuccess", "answers"),
        ("ToolSelection", "exact tool set"),
        ("StepBudget", "step budget"),
        ("LatencyBudget", "latency budget"),
    ):
        passed = sum(1 for case in report.cases if _score(report, case.name, grader) == 1.0)
        _add(f"tuning suite ({len(report.cases)} tasks)", row, passed, len(report.cases))

    # Held-out split: grade the recorded held-out run offline (deterministic).
    if config is not None:
        try:
            from agentic_workflows import evals

            if config.heldout_records_path.exists():
                tasks = (
                    evals.parse_tasks(config.heldout_tasks_path.read_text(encoding="utf-8"))
                    if config.heldout_tasks_path.exists()
                    else list(evals.HELDOUT_SUITE)
                )
                heldout_report = evals.evaluate_records(
                    evals.load_records(config.heldout_records_path), tasks=tasks
                )
                answer_cases = [
                    c for c in heldout_report.cases if c.inputs.expected_behavior == "answer"
                ]
                refuse_cases = [
                    c for c in heldout_report.cases if c.inputs.expected_behavior == "refuse"
                ]
                for grader, row in (
                    ("AnswerSuccess", "answers"),
                    ("ToolSelection", "exact tool set"),
                ):
                    passed = sum(
                        1
                        for case in answer_cases
                        if _score(heldout_report, case.name, grader) == 1.0
                    )
                    _add(f"held-out answers ({len(answer_cases)})", row, passed, len(answer_cases))
                passed = sum(
                    1
                    for case in refuse_cases
                    if _score(heldout_report, case.name, "RefusalSuccess") == 1.0
                )
                _add(
                    f"should-fail probes ({len(refuse_cases)})",
                    "graceful refusals",
                    passed,
                    len(refuse_cases),
                )
        except (OSError, ValueError, KeyError):
            pass  # held-out artifacts missing or unreadable: tuning bars only

    splits = list(dict.fromkeys(split for split, _, _, _ in entries))
    rows = list(dict.fromkeys(row for _, row, _, _ in entries))
    color_cycle = ["#2dd4bf", "#38bdf8", "#a78bfa"]

    fig = go.Figure()
    for index, split in enumerate(splits):
        by_row = {row: (passed, total) for s, row, passed, total in entries if s == split}
        fig.add_bar(
            name=split,
            y=rows,
            x=[float(by_row[row][0]) if row in by_row else None for row in rows],
            text=[f"{by_row[row][0]}/{by_row[row][1]}" if row in by_row else "" for row in rows],
            orientation="h",
            marker={"color": color_cycle[index % len(color_cycle)]},
            textposition="inside",
            hovertemplate="%{y} — " + split + ": %{x:.0f} passed<extra></extra>",
        )

    n_passed = sum(passed for _, _, passed, _ in entries)
    n_total = sum(total for _, _, _, total in entries)
    fig.update_layout(
        barmode="group",
        xaxis={"title": "tasks passed", "range": [0, max(t for _, _, _, t in entries) + 1]},
        yaxis={"title": "", "categoryorder": "array", "categoryarray": rows},
        bargap=0.3,
    )
    apply_theme(fig)
    _takeaway_title(
        fig,
        f"All {n_passed}/{n_total} graded outcomes pass across the three splits",
        "Tuning graded by four deterministic graders, held-out answers by two, "
        "probes by refusal grade.",
    )
    # Legend below the plot (the pinned top legend would crowd the title);
    # clear of the centered x-axis title.
    fig.update_layout(
        legend={"orientation": "h", "yanchor": "top", "y": -0.16, "x": 0, "xanchor": "left"},
        margin={"l": 135, "b": 100},
    )
    return fig


def _fig_tool_usage_matrix(cases: list[Any]) -> go.Figure:
    """Tasks x tools heatmap of per-call counts from the captured tool traces.

    Every cell with calls is annotated with its count, so the over-call noise
    (unplanned ``note_store`` / ``search_documents`` / ``calculator``) reads at
    a glance: one bright cell is a planned call, a bright *column* under a
    tool that few tasks expect is the exact-set miss driver.
    """
    names = [case.name for case in cases]
    matrix: list[list[int]] = []
    for tool in SUITE_TOOLS:
        row: list[int] = []
        for case in cases:
            call_names = [c.name for c in case.output.tool_calls] or list(case.output.tools_used)
            row.append(sum(1 for name in call_names if name == tool))
        matrix.append(row)
    text = [[str(value) if value > 0 else "" for value in row] for row in matrix]
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=matrix,
                x=names,
                y=list(SUITE_TOOLS),
                text=text,
                texttemplate="%{text}",
                showscale=False,
                colorscale=[[0, "#16213a"], [1, "#2dd4bf"]],
                zmin=0,
                hovertemplate="%{y} on %{x}: %{z} call(s)<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        xaxis_title="task",
        yaxis_title="",
    )
    apply_theme(fig)
    # Dynamic takeaway: with zero out-of-set calls the run is clean; otherwise
    # name the tool with the most unplanned invocations.
    extra_totals = {
        tool: sum(
            1
            for case in cases
            for name in ([c.name for c in case.output.tool_calls] or case.output.tools_used)
            if name == tool and tool not in case.inputs.expected_tools
        )
        for tool in SUITE_TOOLS
    }
    expected_by_tool = {
        tool: sum(1 for case in cases if tool in case.inputs.expected_tools) for tool in SUITE_TOOLS
    }
    totals = {tool: sum(row) for tool, row in zip(SUITE_TOOLS, matrix, strict=True)}
    headline = "Tool calls per task x tool — the behavioral x-ray the exact-set grader reads"
    if sum(extra_totals.values()) == 0:
        _takeaway_title(
            fig,
            headline,
            "Zero unplanned calls this run — every invocation lands in a task's expected "
            f"tool set; {totals.get('search_handbook', 0)} handbook reads are the busiest row.",
        )
        return fig
    loudest = max(SUITE_TOOLS, key=lambda t: extra_totals[t])
    loudest_tasks = sum(
        1
        for case in cases
        if any(c.name == loudest for c in case.output.tool_calls)
        or loudest in case.output.tools_used
    )
    _takeaway_title(
        fig,
        headline,
        f"{extra_totals[loudest]} unplanned {loudest} call(s) across "
        f"{loudest_tasks}/{len(cases)} tasks — only {expected_by_tool[loudest]} task(s) "
        "plan for it; a bright column here is an unplanned habit, not a need.",
    )
    return fig


def _fig_node_waterfall(cases: list[Any]) -> go.Figure:
    """Per-task stacked node visits: one segment per ``steps[]`` entry.

    Segment width is that visit's latency; labels are ``plan`` / ``execute``
    (``#2``, ``#3`` for repeat visits — repair and critique-driven re-runs) /
    ``critique``. A runaway task reads as ONE giant segment (t14: ~260 s
    inside a single execute visit), not a stack of retries. The x-range spans
    the data max x 1.15 — no axis-length budget line; the budget is a single
    arrow annotation near the top.
    """
    names = [case.name for case in cases]
    segments: dict[str, dict[str, tuple[float, int, int]]] = {}
    first_pos: dict[str, int] = {}
    for case in cases:
        seen: dict[str, int] = {}
        for pos, trace in enumerate(case.output.steps):
            seen[trace.node] = seen.get(trace.node, 0) + 1
            label = trace.node if seen[trace.node] == 1 else f"{trace.node} #{seen[trace.node]}"
            segments.setdefault(label, {})[case.name] = (
                trace.latency_s,
                trace.input_tokens,
                trace.output_tokens,
            )
            first_pos.setdefault(label, pos)
    labels = sorted(segments, key=lambda label: first_pos[label])

    node_color = {"plan": "#38bdf8", "execute": "#2dd4bf", "critique": "#a78bfa"}
    fig = go.Figure()
    for label in labels:
        node = label.split(" ")[0]
        repeat = label != node
        latencies: list[float] = []
        hover: list[str] = []
        text: list[str] = []
        for name in names:
            visit = segments[label].get(name)
            if visit is None:
                latencies.append(0.0)
                hover.append("")
                text.append("")
            else:
                latency, in_tokens, out_tokens = visit
                latencies.append(latency)
                hover.append(
                    f"{name} · {label}: {latency:.1f}s, {in_tokens} in + {out_tokens} out tokens"
                )
                text.append(f"{latency:.0f}s" if latency >= 60 else "")
        fig.add_bar(
            name=label,
            y=names,
            x=latencies,
            orientation="h",
            marker={
                "color": node_color[node],
                "opacity": 0.65 if repeat else 1.0,
            },
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            text=text,
            textposition="inside",
        )
    budget = max((case.inputs.latency_budget_s for case in cases), default=60.0)
    slowest = max((case.output.duration_s for case in cases), default=0.0)
    # x-range follows the data, not the budget: widest stacked task x 1.15.
    task_totals = [sum(trace.latency_s for trace in case.output.steps) for case in cases]
    data_max = max(task_totals, default=0.0)
    x_max = data_max * 1.15 if data_max else 1.0
    # The budget (60 s) sits beyond the data-driven x-range, so the annotation
    # marks it near the top edge with an arrow instead of a full-height line.
    budget_annotation = {
        "xref": "x",
        "yref": "paper",
        "x": min(budget, x_max * 0.80),
        "y": 0.96,
        "text": f"{budget:.0f} s budget",
        "showarrow": True,
        "arrowhead": 2,
        "arrowsize": 1.2,
        "arrowcolor": "#f472b6",
        "ax": min(budget, x_max * 0.80) - x_max * 0.18,
        "ay": 0.96,
        "font": {"size": 11, "color": "#f472b6"},
    }
    fig.update_layout(
        barmode="stack",
        xaxis={"title": "seconds", "range": [0, x_max]},
        yaxis={"title": "", "autorange": "reversed"},
        # Thicker bars: tighter gap than the theme default.
        bargap=0.15,
        annotations=[budget_annotation],
    )
    apply_theme(fig)
    # Lead with the widest single segment: the "one giant visit" story.
    headline = (
        f"Slowest task finishes in {slowest:.0f} s — far under the {budget:.0f} s "
        "budget; a retry appears as an extra labelled segment, never one long visit"
    )
    widest: tuple[str, str, float] | None = None
    for label, per_task in segments.items():
        for task_name, (latency, _, _) in per_task.items():
            if widest is None or latency > widest[2]:
                widest = (task_name, label, latency)
    if widest is not None:
        task_name, label, latency = widest
        _takeaway_title(
            fig,
            headline,
            f"Widest single segment: {task_name} {label} at {latency:.0f}s — retries add "
            "new labelled segments (#2, #3), they never stretch one visit.",
        )
    else:
        _takeaway_title(fig, headline, "No node visits recorded.")
    # Legend below the plot (the pinned top legend would crowd the title).
    fig.update_layout(
        legend={"orientation": "h", "yanchor": "top", "y": -0.10, "x": 0, "xanchor": "left"},
        margin={"l": 60, "b": 90},
    )
    return fig


def _fig_cost_latency_bars(cases: list[Any], config: EvalConfig | None) -> go.Figure:
    """Stacked tokens + cloud-equivalent cost + latency vs budget (kept)."""
    names = [case.name for case in cases]
    durations = [case.output.duration_s for case in cases]
    budgets = [case.inputs.latency_budget_s for case in cases]
    in_rate = config.usd_per_mtok_input if config is not None else 1.0
    out_rate = config.usd_per_mtok_output if config is not None else 4.0
    input_tokens = [case.output.input_tokens for case in cases]
    output_tokens = [case.output.output_tokens for case in cases]
    costs = [
        (i / 1e6 * in_rate + o / 1e6 * out_rate)
        for i, o in zip(input_tokens, output_tokens, strict=True)
    ]
    totals = [i + o for i, o in zip(input_tokens, output_tokens, strict=True)]
    cost_labels = [f"${c:.4f}" for c in costs]
    fig = go.Figure(
        data=[
            go.Bar(name="input tokens", x=names, y=input_tokens, marker={"color": "#2dd4bf"}),
            go.Bar(name="output tokens", x=names, y=output_tokens, marker={"color": "#38bdf8"}),
            go.Scatter(
                name="cloud-equivalent cost per task",
                x=names,
                y=totals,
                text=cost_labels,
                mode="text",
                textposition="top center",
                textfont={"size": 11, "color": "#fbbf24"},
                # Direct series labels (the $ amounts above the bars) replace
                # the legend entry — a text-mode swatch would render as "Aa".
                showlegend=False,
                hoverinfo="skip",
            ),
            go.Scatter(
                name="latency",
                x=names,
                y=durations,
                mode="lines+markers",
                line={"color": "#a78bfa"},
                yaxis="y2",
            ),
            go.Scatter(
                name="latency budget",
                x=names,
                y=budgets,
                mode="lines",
                line={"dash": "dash", "color": "#f472b6"},
                yaxis="y2",
            ),
        ]
    )
    budget = max(budgets, default=60.0)
    fig.update_layout(
        barmode="stack",
        xaxis_title="task",
        yaxis={"title": "tokens", "range": [0, max(totals, default=1) * 1.2]},
        yaxis2={
            "title": {"text": "seconds", "standoff": 12},
            "overlaying": "y",
            "side": "right",
            "range": [0, budget * 1.15],
        },
        # Legend below the plot (restacked): it used to overlap the title and
        # takeaway when pinned to the top-right.
        legend={"orientation": "h", "yanchor": "top", "y": -0.16, "x": 0, "xanchor": "left"},
    )
    apply_theme(fig)
    # No "$" in this takeaway: plotly parses PAIRS of $...$ in one string as
    # TeX math (escapes do not help), which rendered the amounts as an italic
    # "0.12cloud-equivalent" mess. Single-$ strings (title, bar labels) are
    # safe; multi-amount prose uses "USD".
    _takeaway_title(
        fig,
        f"Tokens, cloud-equivalent cost and latency per task — all inside "
        f"the $0.25 and {budget:.0f} s budgets",
        f"Total {sum(costs):.4f} USD cloud-equivalent (rate card 1.00/4.00 USD per Mtok "
        f"in/out; labelled estimate, membership-quota key); median {statistics.median(costs):.4f} "
        f"per task; latency budget {budgets[0]:.0f}s held for "
        f"{sum(1 for d, b in zip(durations, budgets, strict=True) if d <= b)}/{len(durations)}.",
    )
    # Bottom space for the restacked legend.
    fig.update_layout(margin={"l": 60, "b": 110})
    return fig


def suite_figures(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
    config: EvalConfig | None = None,
) -> dict[str, go.Figure]:
    """The four story figures.

    ``suite_summary`` (outcomes by split) replaced ``per_task_grading`` — an
    all-pass per-task histogram explained nothing — and ``agent_architecture``
    moved to a mermaid diagram in the story/docs; the trajectory views made
    possible by per-call tool capture stay: ``tool_usage_matrix`` (calls per
    task per tool), ``node_waterfall`` (per-visit latency stack), and
    ``cost_latency_bars`` (tokens/cost/latency vs budget).
    """
    cases = list(report.cases)
    return {
        "suite_summary": _fig_suite_summary(report, config),
        "cost_latency_bars": _fig_cost_latency_bars(cases, config),
        "tool_usage_matrix": _fig_tool_usage_matrix(cases),
        "node_waterfall": _fig_node_waterfall(cases),
    }
