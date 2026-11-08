"""Incumbent/challenger comparison: frozen retrieval and explicit selection."""

import json
from pathlib import Path

from rag_agent.challenger import compare_challenger
from rag_agent.config import RAGConfig


def _write_metrics(path: Path, *, faithfulness: float, relevance: float, recall: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rag_agent": {
            "faithfulness": faithfulness,
            "answer_relevance": relevance,
            "context_recall": recall,
            "p50_latency_s": 10.0,
            "p95_latency_s": 20.0,
            "est_cost_usd_per_query": 0.001,
        },
        "ragas": {
            "faithfulness": faithfulness,
            "answer_relevancy": relevance,
            "context_precision": 0.8,
            "context_recall": recall,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_comparison_selects_kimi_only_when_quality_improves(tmp_path: Path) -> None:
    config = RAGConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write_metrics(config.reports_dir / "metrics.json", faithfulness=0.5, relevance=0.6, recall=0.9)
    _write_metrics(challenger_dir / "metrics.json", faithfulness=0.7, relevance=0.8, recall=0.9)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "kimi"
    assert result["deltas"]["faithfulness"] == 0.2
    assert result["deltas"]["context_recall"] == 0.0
    assert (config.reports_dir / "kimi_comparison.json").is_file()
    assert (config.reports_dir / "figures" / "kimi_generation_comparison.json").is_file()


def test_comparison_retains_incumbent_on_recall_regression(tmp_path: Path) -> None:
    config = RAGConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write_metrics(config.reports_dir / "metrics.json", faithfulness=0.5, relevance=0.6, recall=0.9)
    _write_metrics(challenger_dir / "metrics.json", faithfulness=0.7, relevance=0.8, recall=0.8)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "incumbent"
    assert result["deltas"]["context_recall"] == -0.1


def test_comparison_retains_incumbent_on_relevance_regression(tmp_path: Path) -> None:
    config = RAGConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write_metrics(config.reports_dir / "metrics.json", faithfulness=0.5, relevance=0.6, recall=0.9)
    _write_metrics(challenger_dir / "metrics.json", faithfulness=0.7, relevance=0.5, recall=0.9)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "incumbent"
    assert result["deltas"]["answer_relevance"] == -0.1
    assert "deterministic checks" in result["evaluation_note"]


def test_comparison_retains_incumbent_on_faithfulness_regression(tmp_path: Path) -> None:
    config = RAGConfig(reports_dir=tmp_path / "incumbent")
    challenger_dir = tmp_path / "challenger"
    _write_metrics(config.reports_dir / "metrics.json", faithfulness=0.5, relevance=0.6, recall=0.9)
    _write_metrics(challenger_dir / "metrics.json", faithfulness=0.4, relevance=0.8, recall=0.9)

    result = compare_challenger(config, challenger_dir)

    assert result["selected"] == "incumbent"
    assert result["deltas"]["faithfulness"] == -0.1
