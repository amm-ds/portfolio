"""Verify-then-answer loop tests: scripted judges, repair, abstention, thresholds.

All tests are offline: the LLM claim judge is backed by a scripted
FunctionModel that decides support from claim content (claims containing the
word "unsupported" fail; repaired text containing "fixed" passes), and the
deterministic keyword judge needs no model at all.
"""

import json
import re
from typing import Any

import pytest
from portfolio_eval.rag import KeywordJudge
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from rag_agent.config import RAGConfig, VerifyConfig
from rag_agent.evaluate import run_rag_eval
from rag_agent.index import Retriever
from rag_agent.schemas import AnalysisResult, Citation, EvalQuestion
from rag_agent.verify import (
    ABSTENTION_TEXT,
    REPAIR_IMPOSSIBLE,
    KeywordEntailmentJudge,
    LLMEntailmentJudge,
    split_claims,
    verify_result,
)

SUPPORTED_CLAIM = "The evidence states this fact."
UNSUPPORTED_FIXABLE = "This unsupported claim is fixable."
UNSUPPORTED_HOPELESS = "This unsupported claim is hopeless."
REPAIRED_CLAIM = "This fixed claim is supported."


def _last_text(messages: list[Any]) -> str:
    msg = messages[-1]
    parts = getattr(msg, "parts", [msg])
    return " ".join(
        str(p.content) for p in parts if getattr(p, "content", None) and isinstance(p.content, str)
    )


def _scripted_model(messages: list[Any], info: Any) -> ModelResponse:
    """Scripted claim judge + repairer driven by prompt content."""
    last = _last_text(messages)
    if "Unsupported sentence:" in last:
        if "hopeless" in last:
            return ModelResponse(parts=[TextPart(content=REPAIR_IMPOSSIBLE)])
        return ModelResponse(parts=[TextPart(content=REPAIRED_CLAIM)])
    if "Claims to check" in last:
        claims = []
        for line in last.split("Claims to check", 1)[1].strip().splitlines():
            match = re.match(r"^\d+\.\s+(.*)", line.strip())
            if not match:
                continue
            claim = match.group(1).strip()
            claims.append(
                {
                    "claim": claim,
                    "supported": "unsupported" not in claim,
                    "reason": "scripted",
                }
            )
        return ModelResponse(parts=[TextPart(content=json.dumps({"verdicts": claims}))])
    raise AssertionError(f"unexpected prompt: {last[:120]}")


def scripted_judge() -> LLMEntailmentJudge:
    return LLMEntailmentJudge(model=FunctionModel(_scripted_model))


def make_result(
    summary: str, confidence: float = 0.9, excerpt: str = "Evidence text."
) -> AnalysisResult:
    return AnalysisResult(
        summary=summary,
        citations=[
            Citation(
                chunk_id="fake#c000",
                article_id="climate-000",
                title="Fake",
                excerpt=excerpt,
                score=1.0,
            )
        ],
        confidence=confidence,
    )


def run_verify(
    config: RAGConfig,
    retriever: Retriever,
    summary: str,
    judge: Any,
    confidence: float = 0.9,
) -> Any:
    result = make_result(summary, confidence=confidence)
    report = verify_result("question?", result, retriever, config, judge)
    return result, report


def test_split_claims() -> None:
    assert split_claims("One claim. Two claims! Three?") == [
        "One claim.",
        "Two claims!",
        "Three?",
    ]
    assert split_claims("single") == ["single"]


def test_keyword_judge_is_deterministic() -> None:
    judge = KeywordEntailmentJudge()
    verdicts = judge.verify_claims(
        "q?",
        ["The quick brown fox jumps.", "Quantum entanglement enables teleportation."],
        "the quick brown fox jumps over the lazy dog",
    )
    assert [v.supported for v in verdicts] == [True, False]
    # No content words → vacuously supported (nothing to check).
    vacuous = judge.verify_claims("q?", ["Is was?"], "anything at all")
    assert vacuous[0].supported is True


def test_all_supported_keeps_summary(config: RAGConfig, retriever: Retriever) -> None:
    result, report = run_verify(
        config, retriever, f"{SUPPORTED_CLAIM} {SUPPORTED_CLAIM}", scripted_judge()
    )
    assert report.support_fraction == 1.0
    assert report.n_repair_calls == 0
    assert not report.abstained
    assert result.summary == f"{SUPPORTED_CLAIM} {SUPPORTED_CLAIM}"


def test_mixed_claims_repair_path(config: RAGConfig, retriever: Retriever) -> None:
    result, report = run_verify(
        config, retriever, f"{SUPPORTED_CLAIM} {UNSUPPORTED_FIXABLE}", scripted_judge()
    )
    assert report.n_repair_calls == 1
    assert report.support_fraction == 1.0
    assert not report.abstained
    assert REPAIRED_CLAIM in result.summary
    assert SUPPORTED_CLAIM in result.summary
    assert UNSUPPORTED_FIXABLE not in result.summary
    repaired = [c for c in report.claims if c.repaired]
    assert len(repaired) == 1 and repaired[0].supported


def test_unrepairable_claim_dropped_without_abstention(
    config: RAGConfig, retriever: Retriever
) -> None:
    # 2 of 3 claims survive (1 supported + 1 repaired); the hopeless claim is
    # dropped: support 2/3 ≥ 0.6 → answer stands without the dropped claim.
    result, report = run_verify(
        config,
        retriever,
        f"{SUPPORTED_CLAIM} {UNSUPPORTED_FIXABLE} {UNSUPPORTED_HOPELESS}",
        scripted_judge(),
    )
    assert report.n_repair_calls == 2
    assert report.support_fraction == pytest.approx(2 / 3)
    assert not report.abstained
    dropped = [c for c in report.claims if c.dropped]
    assert len(dropped) == 1 and UNSUPPORTED_HOPELESS in dropped[0].claim
    assert UNSUPPORTED_HOPELESS not in result.summary


def test_all_unsupported_falls_back_to_abstention(config: RAGConfig, retriever: Retriever) -> None:
    config = config.model_copy(update={"verify": VerifyConfig(enabled=True, max_repair_calls=0)})
    result, report = run_verify(
        config, retriever, f"{UNSUPPORTED_FIXABLE} {UNSUPPORTED_HOPELESS}", scripted_judge()
    )
    assert report.abstained
    assert report.support_fraction == 0.0
    assert result.summary == ABSTENTION_TEXT
    assert result.confidence < 0.3  # integrates with is_abstention
    assert report.final_summary == ABSTENTION_TEXT


def test_support_at_threshold_keeps_answer(config: RAGConfig, retriever: Retriever) -> None:
    # Exactly at min_support (1/2 = 0.5 with min_support=0.5) → kept, not abstained.
    config = config.model_copy(update={"verify": VerifyConfig(enabled=True, min_support=0.5)})
    result, report = run_verify(
        config,
        retriever,
        f"{SUPPORTED_CLAIM} {UNSUPPORTED_HOPELESS}",
        scripted_judge(),
    )
    assert report.support_fraction == 0.5
    assert not report.abstained
    assert result.summary == SUPPORTED_CLAIM


def test_support_one_below_threshold_abstains(config: RAGConfig, retriever: Retriever) -> None:
    config = config.model_copy(
        update={"verify": VerifyConfig(enabled=True, min_support=0.6, max_repair_calls=0)}
    )
    _, report = run_verify(
        config, retriever, f"{SUPPORTED_CLAIM} {UNSUPPORTED_HOPELESS}", scripted_judge()
    )
    assert report.support_fraction == 0.5
    assert report.abstained


def test_already_abstained_answer_is_skipped(config: RAGConfig, retriever: Retriever) -> None:
    refusal = "No relevant evidence was found in the retrieved passages."
    result, report = run_verify(config, retriever, refusal, scripted_judge(), confidence=0.1)
    assert report.skipped
    assert report.claims == []
    assert result.summary == refusal  # untouched


def test_llm_judge_failure_falls_back_to_keyword(config: RAGConfig, retriever: Retriever) -> None:
    def _boom(messages: list[Any], info: Any) -> ModelResponse:
        raise RuntimeError("provider exploded")

    judge = LLMEntailmentJudge(model=FunctionModel(_boom))
    # Claim fully covered by the citation excerpt → keyword fallback supports it.
    result = make_result("The evidence text.", excerpt="The evidence text.")
    report = verify_result("q?", result, retriever, config, judge)
    assert report.support_fraction == 1.0
    assert not report.abstained


def _canned_analysis_model() -> FunctionModel:
    from portfolio_core.llm import mock_model_for_tests

    payload = json.dumps(
        {
            "summary": "Photosynthesis lets plants convert light energy into chemical energy.",
            "citations": [
                {
                    "chunk_id": "photo-000#c000",
                    "article_id": "photo-000",
                    "title": "Photosynthesis",
                    "excerpt": "Photosynthesis converts light energy into chemical energy.",
                    "score": 1.0,
                }
            ],
            "confidence": 0.9,
        }
    )
    return mock_model_for_tests(payload)


def test_verify_disabled_via_config(config: RAGConfig, retriever: Retriever) -> None:
    # run_rag_eval must not consult the claim judge when verification is off.
    from rag_agent.agent import build_agent

    config = config.model_copy(update={"verify": VerifyConfig(enabled=False)})
    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    agent = build_agent(config, model=_canned_analysis_model())
    rag_run = run_rag_eval(
        config,
        agent,
        retriever,
        questions,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
    )
    assert rag_run.verify_reports == []  # disabled in config → never consulted


def test_run_rag_eval_collects_verify_reports(config: RAGConfig, retriever: Retriever) -> None:
    from rag_agent.agent import build_agent

    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    agent = build_agent(config, model=_canned_analysis_model())
    rag_run = run_rag_eval(
        config,
        agent,
        retriever,
        questions,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
    )
    assert len(rag_run.verify_reports) == 1
    report = rag_run.verify_reports[0]
    assert report.latency_s >= 0.0
    assert report.support_fraction == 1.0  # canned claim is fully covered
    # The verified summary is what reaches the judge + RAGAS rows.
    assert "photosynthesis" in rag_run.ragas_rows[0].answer.lower()
