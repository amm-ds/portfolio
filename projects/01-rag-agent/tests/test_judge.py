"""Judge selection: keyword default, LLM rubric judge behind JUDGE=llm, offline fallback."""

from typing import Any

import pytest
from portfolio_eval.rag import JudgeVerdict, KeywordJudge
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from rag_agent.judge import LLMRubricJudge, RubricJudge, build_judge


def _canned_verdict(score: float = 0.9, reason: str = "supported by context") -> FunctionModel:
    payload = JudgeVerdict(score=score, reason=reason).model_dump_json()

    def _respond(messages: list[Any], info: Any) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=payload)])

    return FunctionModel(_respond)


def test_llm_judge_returns_validated_verdict() -> None:
    judge = LLMRubricJudge(model=_canned_verdict(score=0.85, reason="grounded"))
    verdict = judge.judge("what is X?", "X is a thing.", "X is a thing used for.")
    assert isinstance(verdict, JudgeVerdict)
    assert verdict.score == 0.85
    assert verdict.reason == "grounded"


def test_llm_judge_falls_back_to_keyword_on_failure() -> None:
    def _boom(messages: list[Any], info: Any) -> ModelResponse:
        raise RuntimeError("provider exploded")

    judge = LLMRubricJudge(model=FunctionModel(_boom))
    verdict = judge.judge("what is X?", "context about X", "answer about X")
    assert isinstance(verdict, JudgeVerdict)  # keyword fallback still returns a verdict
    assert 0.0 <= verdict.score <= 1.0


def test_build_judge_defaults_to_keyword_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JUDGE", "llm")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    judge = build_judge()
    assert isinstance(judge, KeywordJudge)


def test_build_judge_respects_keyword_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE", raising=False)
    assert isinstance(build_judge(), KeywordJudge)


def test_rubric_judge_union_is_runtime_compatible() -> None:
    judge: RubricJudge = LLMRubricJudge(model=_canned_verdict())
    assert hasattr(judge, "judge")
