#!/usr/bin/env python3
"""Rebuild the final_v3 figure set from committed artifacts (no LLM calls).

Writes four figures to ``reports/figures/``:

- ``failure_taxonomy``  from ``reports/final_v3_e2e/question_traces_heldout.json``
  (the 120-question final pass verdict classes),
- ``retrieval_ladder``   from ``reports/retrieval_baseline/*.json`` and
  ``reports/retrieval_sweeps/*.json`` (R0-S3 arms across frozen splits),
- ``final_outcome``      from ``reports/final_v3_e2e/f1_summary.json`` (TP/FP/TN/FN)
  plus per-slice correctness recomputed from the committed traces,
- ``verify_funnel``      from ``final_v3_e2e/metrics.json``
  (``detail.final_v3.verify`` claim-loop accounting).

Every number is cross-checked against its committed source; the script fails
loudly on drift instead of writing a figure that disagrees with the reports.

Run: uv run python scripts/build_final_figures.py
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from portfolio_core.plotting import save_html, save_json
from rag_agent.figures import (
    final_outcome_figure,
    retrieval_ladder_figure,
    taxonomy_figure,
    verify_funnel_figure,
)
from rag_agent.reporting import QuestionTrace, classify_question

REPORTS = Path(__file__).resolve().parents[1] / "reports"
FIGURES = REPORTS / "figures"

SPLITS = ["dev_v1", "dev_40", "dev_65", "heldout_55", "final_v3"]
ARMS = {
    "R0": None,  # retrieval_baseline/<split>.json
    "S1": "s1_structure_200",
    "S2": "s2_structure_hybrid_rrf",
    "S3": "s3_structure_hybrid_diverse",
}

EXPECTED_TAXONOMY = {
    "correct": 104,
    "empty-answer": 10,
    "budget-terminated": 4,
    "unsupported-claim": 1,
    "retrieval-miss": 1,
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _expect(condition: bool, message: str) -> None:
    """Fail loudly on drift instead of writing a figure that disagrees."""
    if not condition:
        raise RuntimeError(message)


def _load_traces() -> list[QuestionTrace]:
    raw = _load(REPORTS / "final_v3_e2e" / "question_traces_heldout.json")
    keys = {f.name for f in fields(QuestionTrace)}
    return [QuestionTrace(**{k: v for k, v in t.items() if k in keys}) for t in raw]


def build_failure_taxonomy(traces: list[QuestionTrace]) -> None:
    counts = {label: 0 for label in EXPECTED_TAXONOMY}
    for trace in traces:
        counts[classify_question(trace)] += 1
    _expect(counts == EXPECTED_TAXONOMY, f"taxonomy drifted: {counts}")
    _expect(len(traces) == 120, f"expected 120 traces, got {len(traces)}")
    fig = taxonomy_figure(traces, scope="final_v3 final pass")
    save_json(fig, FIGURES / "failure_taxonomy.json")
    save_html(fig, FIGURES / "failure_taxonomy.html", title="failure_taxonomy")
    print("wrote failure_taxonomy (n=120: 104/10/4/1/1)")


def build_retrieval_ladder() -> None:
    rows: list[dict[str, Any]] = []
    for arm, sweep in ARMS.items():
        for split in SPLITS:
            if sweep is None:
                path = REPORTS / "retrieval_baseline" / f"{split}.json"
            else:
                path = REPORTS / "retrieval_sweeps" / f"{sweep}__{split}.json"
            if not path.exists():
                continue
            metrics = _load(path)["metrics"]
            rows.append(
                {
                    "arm": arm,
                    "split": split,
                    "n": metrics["n_answerable"],
                    "recall_at_5": metrics["recall_at_5"],
                    "wilson95": metrics["recall_at_5_wilson95"],
                    "all_articles_at_5": metrics.get("all_articles_at_5"),
                }
            )
    s3_final = next(r for r in rows if r["arm"] == "S3" and r["split"] == "final_v3")
    _expect(abs(s3_final["recall_at_5"] - 0.9456521739130435) < 1e-9, f"{s3_final}")
    # S1/S2 were never measured on final_v3 (set consumed after the S3 gate);
    # the ladder must not invent those cells.
    _expect(
        not any(r["split"] == "final_v3" and r["arm"] in ("S1", "S2") for r in rows),
        "S1/S2 final_v3 cells must stay absent (set consumed)",
    )
    fig = retrieval_ladder_figure(rows)
    save_json(fig, FIGURES / "retrieval_ladder.json")
    save_html(fig, FIGURES / "retrieval_ladder.html", title="retrieval_ladder")
    print(f"wrote retrieval_ladder ({len(rows)} committed cells)")


def build_final_outcome(traces: list[QuestionTrace]) -> None:
    summary = _load(REPORTS / "final_v3_e2e" / "f1_summary.json")
    _expect(
        (summary["tp"], summary["fp"], summary["tn"], summary["fn"]) == (80, 4, 24, 12),
        f"confusion drifted: {summary}",
    )
    slices: dict[str, tuple[int, int]] = {}
    for trace in traces:
        key = trace.category if trace.expected_behavior == "answer" else "unanswerable"
        correct, total = slices.get(key, (0, 0))
        slices[key] = (correct + (classify_question(trace) == "correct"), total + 1)
    _expect(
        slices == {"single_hop": (60, 68), "multi_hop": (20, 24), "unanswerable": (24, 28)},
        f"slices drifted: {slices}",
    )
    fig = final_outcome_figure(summary, slices)
    save_json(fig, FIGURES / "final_outcome.json")
    save_html(fig, FIGURES / "final_outcome.html", title="final_outcome")
    print("wrote final_outcome (TP 80 / FP 4 / TN 24 / FN 12; 60/68, 20/24, 24/28)")


def build_verify_funnel() -> None:
    verify = _load(REPORTS / "final_v3_e2e" / "metrics.json")["detail"]["final_v3"]["verify"]
    expected = {
        "n_drafted": 166,
        "n_mechanical_fail": 16,
        "n_judged": 150,
        "n_judge_supported": 148,
        "n_surviving": 159,
        "n_dropped": 7,
        "n_accepted_original": 148,
        "n_accepted_repaired": 11,
        "n_dropped_original": 3,
        "n_dropped_repaired": 4,
    }
    for key, value in expected.items():
        _expect(verify[key] == value, f"{key}: {verify[key]} != {value}")
    fig = verify_funnel_figure(verify)
    save_json(fig, FIGURES / "verify_funnel.json")
    save_html(fig, FIGURES / "verify_funnel.html", title="verify_funnel")
    print("wrote verify_funnel (166 → 16 → 150 → 148 → 159 / 7)")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    traces = _load_traces()
    build_failure_taxonomy(traces)
    build_retrieval_ladder()
    build_final_outcome(traces)
    build_verify_funnel()


if __name__ == "__main__":
    main()
