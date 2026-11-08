"""Incumbent-vs-hosted generation comparison, with no retrieval changes."""

import json
from pathlib import Path
from typing import Any, cast

import plotly.graph_objects as go
from portfolio_core.config import get_settings
from portfolio_core.plotting import add_takeaway, apply_theme, save_json

from rag_agent.config import RAGConfig


def _metrics(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _comparison_figure(incumbent: dict[str, Any], challenger: dict[str, Any]) -> go.Figure:
    rows = [
        ("faithfulness", "rag_agent", "faithfulness"),
        ("answer relevance", "rag_agent", "answer_relevance"),
        ("RAGAS faithfulness", "ragas", "faithfulness"),
        ("RAGAS relevancy", "ragas", "answer_relevancy"),
        ("context recall", "rag_agent", "context_recall"),
    ]
    labels = [row[0] for row in rows]
    before = [float(incumbent[block][key]) for _, block, key in rows]
    after = [float(challenger[block][key]) for _, block, key in rows]
    fig = go.Figure()
    fig.add_bar(x=labels, y=before, name="incumbent")
    fig.add_bar(x=labels, y=after, name="Kimi challenger")
    fig.update_layout(
        title="Grounded generation — same retrieval, different model",
        barmode="group",
        yaxis_title="score",
        yaxis_range=[0, 1],
    )
    add_takeaway(
        fig, "retrieval index and questions are frozen; only the generation provider changes"
    )
    return apply_theme(fig)


def compare_challenger(config: RAGConfig, challenger_dir: Path) -> dict[str, Any]:
    """Write a machine-readable comparison and its Plotly figure."""
    incumbent = _metrics(config.reports_dir / "metrics.json")
    challenger = _metrics(challenger_dir / "metrics.json")
    keys = [
        ("faithfulness", "rag_agent", "faithfulness"),
        ("answer_relevance", "rag_agent", "answer_relevance"),
        ("ragas_faithfulness", "ragas", "faithfulness"),
        ("ragas_answer_relevancy", "ragas", "answer_relevancy"),
        ("context_recall", "rag_agent", "context_recall"),
    ]
    deltas = {
        name: round(float(challenger[block][key]) - float(incumbent[block][key]), 6)
        for name, block, key in keys
    }
    selected = (
        "kimi"
        if deltas["faithfulness"] > 0
        and deltas["answer_relevance"] > 0
        and deltas["context_recall"] >= -0.02
        else "incumbent"
    )
    model = get_settings().llm_model or "configured-hosted-model"
    result = {
        "selected": selected,
        "challenger_model": model,
        "deltas": deltas,
        "incumbent": {
            key: incumbent["rag_agent"][key]
            for key in [
                "faithfulness",
                "answer_relevance",
                "context_recall",
                "p50_latency_s",
                "p95_latency_s",
                "est_cost_usd_per_query",
            ]
        },
        "challenger": {
            key: challenger["rag_agent"][key]
            for key in [
                "faithfulness",
                "answer_relevance",
                "context_recall",
                "p50_latency_s",
                "p95_latency_s",
                "est_cost_usd_per_query",
            ]
        },
        "ragas": {"incumbent": incumbent["ragas"], "challenger": challenger["ragas"]},
        "evaluation_note": (
            "The retrieval index and questions are unchanged. RAGAS uses the same hosted "
            "provider as challenger and evaluator, so deterministic checks and failure "
            "inspection remain necessary alongside model-judged scores."
        ),
    }
    output = config.reports_dir / "kimi_comparison.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    save_json(
        _comparison_figure(incumbent, challenger),
        config.reports_dir / "figures" / "kimi_generation_comparison.json",
    )
    return result
