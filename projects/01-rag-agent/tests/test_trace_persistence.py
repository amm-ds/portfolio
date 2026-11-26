"""Phase-2b: answer/claims persistence on question traces (offline, fakes only).

The E8 audit found the committed final_v3 E2E run persisted only question
traces — the answer texts and per-claim verdicts were never written, blocking
any second-judge re-grade. These tests pin the wiring that makes a rerun
produce gradeable artifacts: the trace fields, the checkpoint writer
(``reports/runs/<id>/rows.jsonl``), the final ``question_traces.json``, and
the offline rebuild reader. No network, no hosted calls.
"""

import json
from pathlib import Path

import pytest
from portfolio_core.llm import mock_model_for_tests
from portfolio_eval.rag import KeywordJudge
from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig
from rag_agent.evaluate import run_rag_eval, sweep_figure
from rag_agent.index import Retriever
from rag_agent.reporting import (
    QuestionTrace,
    RetrievalScores,
    rebuild_report_from_artifacts,
    trace_to_row,
    write_question_traces,
    write_reports,
)
from rag_agent.runner import Checkpoint, RunManifest, make_run_id
from rag_agent.schemas import EvalQuestion
from rag_agent.verify import ABSTENTION_TEXT, KeywordEntailmentJudge

CANNED_SUMMARY = "Test-only canned answer."
CANNED_ANALYSIS_JSON = json.dumps(
    {
        "summary": CANNED_SUMMARY,
        "citations": [
            {"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e", "score": 1.0}
        ],
        "confidence": 0.5,
    }
)

CLAIM_KEYS = {"claim", "supported", "reason", "repaired", "dropped", "terminal_state"}


def _scores() -> list[RetrievalScores]:
    return [
        RetrievalScores(
            chunk_size=50, recall_at_5=1.0, recall_at_10=1.0, mrr_at_5=1.0, n_questions=1
        )
    ]


def _manifest(split: str = "final_v4", set_sha: str = "b" * 64) -> RunManifest:
    return RunManifest(
        run_id=make_run_id(split, set_sha),
        config_hash="c" * 16,
        commit="deadbeef",
        dirty=False,
        split=split,
        set_sha256=set_sha,
        index_id="minilm:50+rerank:False",
        judge_model="keyword",
        judge_prompt_hash="p" * 16,
    )


def _run_one_question(
    config: RAGConfig, retriever: Retriever, checkpoint: Checkpoint | None = None
):
    agent = build_agent(config, model=mock_model_for_tests(CANNED_ANALYSIS_JSON))
    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    return run_rag_eval(
        config,
        agent,
        retriever,
        questions,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
        checkpoint=checkpoint,
    )


def test_answer_and_claims_round_trip_through_checkpoint_and_rebuild(
    config: RAGConfig, retriever: Retriever, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(a) A trace with answer+claims survives the checkpoint writer and the
    rebuild reader with identical values."""
    checkpoint = Checkpoint.open(tmp_path / "runs" / "final_v4-bbbbbbbbbbbb", _manifest())
    rag_run = _run_one_question(config, retriever, checkpoint=checkpoint)
    trace = rag_run.traces[0]
    assert trace.answer is not None
    assert trace.claims is not None
    assert all(set(c) == CLAIM_KEYS for c in trace.claims)

    # Checkpoint writer: rows.jsonl carries the same answer + claims.
    rows = [
        json.loads(line)
        for line in (checkpoint.run_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["trace"]["answer"] == trace.answer
    assert rows[0]["trace"]["claims"] == trace.claims

    # Final artifact + rebuild reader: question_traces.json written by
    # write_question_traces, read back by rebuild_report_from_artifacts.
    scores = _scores()
    figures = {"chunk_size_sweep": sweep_figure(scores)}
    write_reports(config, scores, rag_run, figures, {"n_questions": 1})
    traces_path = write_question_traces(config, rag_run.traces)
    written = json.loads(traces_path.read_text(encoding="utf-8"))
    assert written[0]["answer"] == trace.answer
    assert written[0]["claims"] == trace.claims

    captured: list[QuestionTrace] = []
    monkeypatch.setattr(
        "rag_agent.reporting.inject_trace_section",
        lambda cfg, traces: captured.extend(traces),
    )
    rebuild_report_from_artifacts(config)
    assert len(captured) == 1
    assert captured[0].answer == trace.answer
    assert captured[0].claims == trace.claims


def test_old_schema_trace_without_answer_claims_still_loads(
    config: RAGConfig, retriever: Retriever, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) A pre-phase-2b row (the committed final_v3 shape) loads with both
    fields at their None defaults, and a default trace serializes WITHOUT the
    new keys — old artifacts stay byte-compatible."""
    # The committed final_v3 row shape: no answer/claims keys at all.
    old_row = {
        "question": "why are plants green",
        "category": "single_hop",
        "expected_behavior": "answer",
        "top_rank": 1,
        "retrieved_relevant": True,
        "cited_relevant": True,
        "faithfulness": 0.9,
        "abstained": False,
        "format_ok": True,
        "output_retries": 0,
        "verdict": "correct",
        "error": "",
        "gate_coverage": 1.0,
        "gate_max_similarity": 0.9,
        "evidence_score": 0.96,
        "n_surviving_claims": 1,
        "budget_terminated": False,
        "gate_refused": False,
        "claim_states": {"accepted_original": 1},
    }
    scores = _scores()
    figures = {"chunk_size_sweep": sweep_figure(scores)}
    write_reports(config, scores, None, figures, {"n_questions": 1})
    (config.reports_dir / "question_traces.json").write_text(
        json.dumps([old_row]) + "\n", encoding="utf-8"
    )
    captured: list[QuestionTrace] = []
    monkeypatch.setattr(
        "rag_agent.reporting.inject_trace_section",
        lambda cfg, traces: captured.extend(traces),
    )
    rebuild_report_from_artifacts(config)
    assert len(captured) == 1
    assert captured[0].answer is None
    assert captured[0].claims is None
    assert captured[0].n_surviving_claims == 1  # old fields unaffected

    # A trace built without the new fields serializes with no new keys.
    row = trace_to_row(captured[0])
    assert "answer" not in row
    assert "claims" not in row


def test_trace_answer_equals_pipeline_emitted_answer(
    config: RAGConfig, retriever: Retriever
) -> None:
    """(c) The persisted answer is exactly the answer the pipeline emitted —
    the post-verify summary when verification runs, the raw agent summary
    when it does not."""
    # Verify ON (the E2E configuration): the canned answer's single claim is
    # unsupported by its evidence and the keyword judge has no repair path,
    # so the pipeline emits the abstention fallback — that is the text the
    # trace must carry, alongside the dropped claim's verdict.
    rag_run = _run_one_question(config, retriever)
    trace = rag_run.traces[0]
    report = rag_run.verify_reports[0]
    assert trace.answer == report.final_summary == ABSTENTION_TEXT
    assert trace.claims is not None and len(trace.claims) == 1
    claim = trace.claims[0]
    assert claim["claim"] == CANNED_SUMMARY
    assert claim["supported"] is False
    assert claim["dropped"] is True
    assert claim["terminal_state"] == "dropped_original"

    # Verify OFF: the emitted answer is the raw agent summary, no claims.
    config.verify.enabled = False
    rag_run = _run_one_question(config, retriever)
    trace = rag_run.traces[0]
    assert trace.answer == CANNED_SUMMARY
    assert trace.claims is None
