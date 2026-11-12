"""Schema validation: platform model config (strict, whitespace-stripped) applies."""

from typing import Any

import pytest
from pydantic import ValidationError
from rag_agent.schemas import AnalysisResult, Article, Chunk, Citation, EvalQuestion


def test_article_valid_and_strips_whitespace() -> None:
    article = Article(article_id=" a ", title="  Climate change ", topic=" Climate ", text=" x ")
    assert article.title == "Climate change"
    assert article.topic == "Climate"


def test_article_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Article(  # type: ignore[call-arg]
            article_id="a", title="t", topic="t", text="x", surprise=1
        )


def test_article_rejects_empty_values() -> None:
    with pytest.raises(ValidationError):
        Article(article_id="a", title="", topic="t", text="x")


def test_citation_score_must_be_nonnegative() -> None:
    with pytest.raises(ValidationError):
        Citation(chunk_id="c", article_id="a", title="t", excerpt="e", score=-0.1)


def test_analysis_result_confidence_bounds() -> None:
    base: dict[str, Any] = {
        "summary": "s",
        "citations": [{"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e"}],
    }
    AnalysisResult(**base, confidence=0.0)
    AnalysisResult(**base, confidence=1.0)
    with pytest.raises(ValidationError):
        AnalysisResult(**base, confidence=1.01)
    with pytest.raises(ValidationError):
        AnalysisResult(**base, confidence=-0.01)


def test_analysis_result_allows_empty_citations_for_abstention() -> None:
    """R6: the honest refusal shape is summary + confidence<0.3 + NO citations.

    The pre-R6 min_length=1 citation mandate made abstention unrepresentable
    and sent the agent into a tool loop on unanswerable questions (Wave Hub,
    stress pass A). Non-abstention answers with empty citations are still
    rejected downstream — by the entailment judge, not the schema.
    """
    result = AnalysisResult(
        summary="The retrieved passages do not answer this.", citations=[], confidence=0.2
    )
    assert result.citations == [] and result.claims == []


def test_eval_question_requires_relevant_articles() -> None:
    with pytest.raises(ValidationError):
        EvalQuestion(question="q?", relevant_article_ids=[])
    q = EvalQuestion(question=" q? ", relevant_article_ids=["a1"])
    assert q.relevant_article_ids == ["a1"]


def test_chunk_token_count_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Chunk(chunk_id="c", article_id="a", text="t", token_count=0)
