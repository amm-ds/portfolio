"""G4 amendment tests: optional answer/claims fields on QuestionTrace.

A trace built without the new fields must serialize exactly as before the
amendment; populated fields must round-trip verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

from rag_agent.config import RAGConfig
from rag_agent.reporting import QuestionTrace, write_question_traces

PRE_AMENDMENT_KEYS = (
    "question",
    "category",
    "expected_behavior",
    "top_rank",
    "retrieved_relevant",
    "cited_relevant",
    "faithfulness",
    "abstained",
    "format_ok",
    "output_retries",
    "verdict",
    "error",
    "gate_coverage",
    "gate_max_similarity",
    "evidence_score",
    "n_surviving_claims",
    "budget_terminated",
    "gate_refused",
    "claim_states",
)


def _trace(**overrides: object) -> QuestionTrace:
    fields: dict[str, object] = {
        "question": "q?",
        "category": "single_hop",
        "expected_behavior": "answer",
        "top_rank": 1,
        "retrieved_relevant": True,
        "cited_relevant": True,
        "faithfulness": 0.9,
        "abstained": False,
        "format_ok": True,
    }
    fields.update(overrides)
    return QuestionTrace(**fields)  # type: ignore[arg-type]


def test_trace_without_new_fields_serializes_exactly_as_before(tmp_path: Path) -> None:
    config = RAGConfig(reports_dir=tmp_path)
    out = write_question_traces(config, [_trace()], path=tmp_path / "traces.json")
    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert tuple(row) == PRE_AMENDMENT_KEYS


def test_answer_and_claims_round_trip(tmp_path: Path) -> None:
    claims = [
        {
            "claim": "The sky is blue.",
            "evidence_span": "the evidence states the sky is blue",
            "label": "supported",
            "state": "accepted_original",
        },
        {
            "claim": "The moon is cheese.",
            "evidence_span": "no matching span",
            "label": "unsupported",
            "state": "dropped_original",
        },
    ]
    config = RAGConfig(reports_dir=tmp_path)
    trace = _trace(answer="The sky is blue.", claims=claims)
    out = write_question_traces(config, [trace], path=tmp_path / "traces.json")
    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert row["answer"] == "The sky is blue."
    assert row["claims"] == claims
    assert "answer" in row and "claims" in row


def test_failure_branch_keeps_none_defaults(tmp_path: Path) -> None:
    config = RAGConfig(reports_dir=tmp_path)
    trace = _trace(format_ok=False, error="boom")
    out = write_question_traces(config, [trace], path=tmp_path / "traces.json")
    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert "answer" not in row and "claims" not in row
