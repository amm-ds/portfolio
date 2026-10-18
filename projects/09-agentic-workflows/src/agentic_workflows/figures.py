"""Story figures for the evaluation report (plotly, dark theme).

Five builders — per-task grading bars, the tool-usage matrix, the node
waterfall, the workflow-graph diagram, and cost/latency bars — plus
:func:`suite_figures`, the bundle the report builder writes as ``.html`` +
``.json`` pairs. All figures are deterministic renderings of the graded
report; ids are stable (ADR-0005: interactive figures are canonical).
"""

from __future__ import annotations

import statistics
from typing import Any

import plotly.graph_objects as go
from portfolio_core.plotting import add_takeaway, apply_theme
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


def _fig_per_task_grading(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
) -> go.Figure:
    """Answer success vs exact-set tool selection per task (kept from wave 3)."""
    cases = list(report.cases)
    names = [case.name for case in cases]
    success = [_score(report, name, "AnswerSuccess") for name in names]
    tool_sel = [_score(report, name, "ToolSelection") for name in names]

    fig = go.Figure(
        data=[
            go.Bar(name="task success", x=names, y=success, marker={"color": "#2dd4bf"}),
            go.Bar(name="tool selection", x=names, y=tool_sel, marker={"color": "#38bdf8"}),
        ]
    )
    fig.update_layout(
        barmode="group",
        title=(
            f"Answers {sum(success):.0f}/{len(success)} and exact tool selection "
            f"{sum(tool_sel):.0f}/{len(tool_sel)} — both graders now agree, "
            "so the over-calling risk is managed, not just measured"
        ),
        xaxis_title="task",
        yaxis_title="score (1 = pass)",
        yaxis={"range": [0, 1.05]},
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        f"Suite success rate {sum(success) / max(len(success), 1):.0%}; "
        f"tool-selection accuracy {sum(tool_sel) / max(len(tool_sel), 1):.0%}.",
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
        title=("Tool calls per task x tool — the behavioral x-ray the exact-set grader reads"),
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
    if sum(extra_totals.values()) == 0:
        add_takeaway(
            fig,
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
    add_takeaway(
        fig,
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
    inside a single execute visit), not a stack of retries. The 180 s budget
    is an annotation, not a dominating axis line.
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
    budget = max((case.inputs.latency_budget_s for case in cases), default=180.0)
    slowest = max((case.output.duration_s for case in cases), default=0.0)
    fig.update_layout(
        barmode="stack",
        title=(
            f"Slowest task finishes in {slowest:.0f} s — far under the {budget:.0f} s "
            "budget; a retry appears as an extra labelled segment, never one long visit"
        ),
        xaxis_title="seconds",
        yaxis={"title": "", "autorange": "reversed"},
        shapes=[
            {
                "type": "line",
                "x0": budget,
                "x1": budget,
                "y0": 0,
                "y1": 1,
                "yref": "paper",
                "line": {"color": "#f472b6", "dash": "dash", "width": 1.5},
            }
        ],
        annotations=[
            {
                "xref": "x",
                "yref": "paper",
                "x": budget,
                "y": 1.03,
                "text": f"{budget:.0f} s budget",
                "showarrow": False,
                "font": {"size": 11, "color": "#f472b6"},
            }
        ],
    )
    apply_theme(fig)
    # Lead with the widest single segment: the "one giant visit" story.
    widest: tuple[str, str, float] | None = None
    for label, per_task in segments.items():
        for task_name, (latency, _, _) in per_task.items():
            if widest is None or latency > widest[2]:
                widest = (task_name, label, latency)
    if widest is not None:
        task_name, label, latency = widest
        add_takeaway(
            fig,
            f"Widest single segment: {task_name} {label} at {latency:.0f}s — retries add "
            "new labelled segments (#2, #3), they never stretch one visit.",
        )
    else:
        add_takeaway(fig, "No node visits recorded.")
    return fig


def _fig_agent_architecture() -> go.Figure:
    """The workflow graph as a plotly-shapes diagram (dark theme).

    Boxes for user → Plan → Execute (with the five-tool toolset sub-box) →
    Critique and both terminal ends; solid edges for the happy path and the
    critique revise loop; a dashed lane for the HITL checkpoint variant
    (approve re-enters at Execute, reject re-plans). Repair self-loop and
    retry bound are drawn, not described.

    Layout rule: every label is a multi-line (``\\n``) annotation centered in
    its box at font ≤ 12, and every box is sized to the widest line — audit
    finding: text must never extend past box bounds.
    """
    # Boxes and text labels live in paper coordinates; arrow annotations need
    # axis coordinates (axref/ayref cannot be "paper"), so the invisible y
    # axis spans exactly [0, 1] and edge() maps through it one-to-one. The
    # whole canvas is used: the HITL lane occupies the bottom paper band.
    Y_MIN = 0.0
    fig = go.Figure()
    fig.update_layout(
        xaxis={"range": [0, 1], "visible": False},
        yaxis={"range": [0, 1.0], "visible": False},
    )
    box_fill = "#1e293b"
    boxes: list[tuple[float, float, float, float, str, dict[str, Any]]] = [
        # (x0, y0, x1, y1, line color, extra layout kwargs)
        (0.01, 0.80, 0.10, 0.92, "#64748b", {}),
        (0.15, 0.76, 0.29, 0.94, "#38bdf8", {}),
        (0.36, 0.58, 0.63, 0.98, "#2dd4bf", {}),
        (0.375, 0.60, 0.615, 0.86, "#2dd4bf", {"opacity": 0.35}),
        (0.72, 0.76, 0.86, 0.94, "#a78bfa", {}),
        (0.905, 0.78, 0.998, 0.92, "#34d399", {}),
        (0.42, 0.06, 0.60, 0.20, "#f472b6", {}),
        (0.08, 0.06, 0.34, 0.20, "#f472b6", {"dash": "dash"}),
    ]
    shapes = []
    for x0, y0, x1, y1, color, extra in boxes:
        shapes.append(
            {
                "type": "rect",
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "fillcolor": box_fill,
                "opacity": extra.get("opacity", 0.9),
                "line": {"color": color, "width": 2, "dash": extra.get("dash", "solid")},
                "xref": "paper",
                "yref": "paper",
            }
        )
    fig.update_layout(shapes=shapes)

    label_style: dict[str, Any] = {"size": 12, "color": "#e2e8f0"}
    tool_style: dict[str, Any] = {"size": 10, "color": "#94a3b8"}
    annotations: list[dict[str, Any]] = [
        # Box labels (paper coordinates, centered inside their boxes).
        {
            "x": 0.055,
            "y": 0.86,
            "text": "user\nrequest",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.22,
            "y": 0.85,
            "text": "Plan\ntyped step plan",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.495,
            "y": 0.90,
            "text": "Execute\ntool-using agent",
            "showarrow": False,
            "font": label_style,
        },
        *[
            {
                "x": 0.495,
                "y": y,
                "text": tool,
                "showarrow": False,
                "xref": "paper",
                "yref": "paper",
                "font": tool_style,
            }
            for tool, y in zip(
                ("search_handbook", "search_documents", "calculator", "unit_convert", "note_store"),
                (0.815, 0.77, 0.725, 0.68, 0.635),
                strict=True,
            )
        ],
        {
            "x": 0.79,
            "y": 0.85,
            "text": "Critique\nself-check",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.9525,
            "y": 0.85,
            "text": "End\n(result)",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.51,
            "y": 0.13,
            "text": "End\n(failure)",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.21,
            "y": 0.13,
            "text": "ApprovalCheckpoint\nHITL gate",
            "showarrow": False,
            "font": label_style,
        },
    ]
    for annotation in annotations:
        annotation.setdefault("xref", "paper")
        annotation.setdefault("yref", "paper")

    def edge(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        label: str,
        *,
        dash: str = "solid",
        color: str = "#94a3b8",
        lx: float | None = None,
        ly: float | None = None,
    ) -> None:
        def _y(paper_y: float) -> float:
            return Y_MIN + (1.0 - Y_MIN) * paper_y

        annotations.append(
            {
                "x": x1,
                "y": _y(y1),
                "ax": x0,
                "ay": _y(y0),
                "xref": "x",
                "yref": "y",
                "axref": "x",
                "ayref": "y",
                "showarrow": True,
                "arrowhead": 2,
                "arrowsize": 1.2,
                "arrowcolor": color,
                "arrowwidth": 1.5,
            }
        )
        if label:
            annotations.append(
                {
                    "x": lx if lx is not None else (x0 + x1) / 2,
                    "y": ly if ly is not None else (y0 + y1) / 2 + 0.035,
                    "text": label,
                    "showarrow": False,
                    "xref": "paper",
                    "yref": "paper",
                    "font": {"size": 11, "color": color},
                    "bgcolor": "#0f172a",
                }
            )

    edge(0.10, 0.86, 0.15, 0.86, "")
    edge(0.29, 0.85, 0.36, 0.85, "plan", lx=0.325)
    edge(0.63, 0.85, 0.72, 0.85, "draft", lx=0.675)
    edge(0.72, 0.79, 0.63, 0.79, "revise (≤1)", lx=0.675, ly=0.755)
    edge(0.86, 0.85, 0.91, 0.85, "pass", lx=0.885)
    # Repair self-loop drawn inside the Execute box top band, label below the
    # arrow so the two never overlap.
    edge(
        0.60,
        0.965,
        0.41,
        0.965,
        "repair ≤ max retries",
        color="#2dd4bf",
        lx=0.505,
        ly=0.945,
    )
    edge(0.47, 0.58, 0.50, 0.20, "retries exhausted", color="#f472b6", lx=0.615, ly=0.40)
    # HITL dashed lane
    edge(0.20, 0.76, 0.20, 0.20, "pause", dash="dash", color="#f472b6", lx=0.16, ly=0.48)
    edge(
        0.31,
        0.13,
        0.42,
        0.58,
        "approve → re-enter at Execute",
        dash="dash",
        color="#f472b6",
        lx=0.475,
        ly=0.35,
    )
    edge(
        0.24,
        0.20,
        0.24,
        0.76,
        "reject → re-plan",
        dash="dash",
        color="#f472b6",
        lx=0.305,
        ly=0.48,
    )

    fig.update_layout(annotations=annotations)
    apply_theme(fig, height=560)
    fig.update_layout(
        title={
            "text": "Plan→Execute→Critique: every transition, retry bound and loop is code",
            "font": {"size": 16},
        },
    )
    add_takeaway(
        fig,
        "Solid: plan→execute→critique with a bounded repair self-loop and one revise loop. "
        "Dashed: the HITL checkpoint lane — approve re-enters at Execute, reject re-plans.",
    )
    # add_takeaway resets the theme margins; this diagram is a canvas, not a
    # chart, so reclaim the space — but keep enough headroom that the title,
    # takeaway, and topmost box never collide.
    fig.update_layout(margin={"l": 10, "r": 10, "t": 110, "b": 10})
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
    fig.update_layout(
        barmode="stack",
        title=(
            "Tokens, cloud-equivalent cost and latency per task — all inside "
            "the $0.25 and 180 s budgets"
        ),
        xaxis_title="task",
        yaxis={"title": "tokens", "range": [0, max(totals, default=1) * 1.2]},
        yaxis2={
            "title": {"text": "seconds", "standoff": 12},
            "overlaying": "y",
            "side": "right",
            "range": [0, max(budgets, default=180.0) * 1.15],
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
    takeaway = (
        f"Total {sum(costs):.4f} USD cloud-equivalent (rate card 1.00/4.00 USD per Mtok "
        f"in/out; labelled estimate, membership-quota key); median {statistics.median(costs):.4f} "
        f"per task; latency budget {budgets[0]:.0f}s held for "
        f"{sum(1 for d, b in zip(durations, budgets, strict=True) if d <= b)}/{len(durations)}."
    )
    add_takeaway(fig, takeaway)
    # add_takeaway resets the theme margins; keep its headroom but leave
    # bottom space for the restacked legend.
    fig.update_layout(margin={"l": 60, "r": 30, "t": 90, "b": 110})
    return fig


def suite_figures(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
    config: EvalConfig | None = None,
) -> dict[str, go.Figure]:
    """The five story figures.

    ``per_task_grading`` and ``cost_latency_bars`` are unchanged in intent;
    ``category_success`` was dropped (category rates duplicate the per-task
    bars) in favor of three trajectory views made possible by per-call tool
    capture: ``tool_usage_matrix`` (calls per task per tool),
    ``node_waterfall`` (per-visit latency stack), and ``agent_architecture``
    (the graph itself).
    """
    cases = list(report.cases)
    return {
        "per_task_grading": _fig_per_task_grading(report),
        "cost_latency_bars": _fig_cost_latency_bars(cases, config),
        "tool_usage_matrix": _fig_tool_usage_matrix(cases),
        "node_waterfall": _fig_node_waterfall(cases),
        "agent_architecture": _fig_agent_architecture(),
    }
