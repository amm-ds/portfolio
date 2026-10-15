"""Judge selection: LLM rubric judge by default when a provider exists, keyword fallback."""

from typing import Any

import pytest
from portfolio_eval.rag import JudgeVerdict, KeywordJudge
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from rag_agent import judge as judge_module
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


def test_build_judge_uses_llm_when_provider_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(judge_module, "provider_available", lambda: True)
    sentinel = object()
    monkeypatch.setattr(judge_module, "LLMRubricJudge", lambda model=None: sentinel)
    assert build_judge() is sentinel


def test_build_judge_falls_back_to_keyword_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(judge_module, "provider_available", lambda: False)
    monkeypatch.delenv("JUDGE", raising=False)
    assert isinstance(build_judge(), KeywordJudge)


def test_build_judge_keyword_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(judge_module, "provider_available", lambda: True)
    assert isinstance(build_judge(prefer="keyword"), KeywordJudge)
    monkeypatch.setenv("JUDGE", "keyword")
    assert isinstance(build_judge(), KeywordJudge)


def test_rubric_judge_union_is_runtime_compatible() -> None:
    judge: RubricJudge = LLMRubricJudge(model=_canned_verdict())
    assert hasattr(judge, "judge")
