"""Agent tests: structured output validation with an injected FunctionModel."""

from typing import Any

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from rag_agent.agent import MOCK_ANALYSIS_JSON, build_agent
from rag_agent.config import RAGConfig
from rag_agent.index import Retriever
from rag_agent.schemas import AnalysisResult


def canned_model(response: str = MOCK_ANALYSIS_JSON) -> FunctionModel:
    def _respond(messages: list[Any], info: Any) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=response)])

    return FunctionModel(_respond)


def test_agent_output_is_validated_analysis_result(config: RAGConfig, retriever: Retriever) -> None:
    agent = build_agent(config, model=canned_model())
    result = agent.run_sync("what is photosynthesis?", deps=retriever)
    assert isinstance(result.output, AnalysisResult)
    assert result.output.confidence == 0.5
    assert len(result.output.citations) == 1
    assert result.output.citations[0].chunk_id == "climate-000#c000"


def test_agent_rejects_invalid_canned_output(config: RAGConfig, retriever: Retriever) -> None:
    # confidence=2.0 violates the 0..1 bound of AnalysisResult: after output
    # retries are exhausted the run fails loudly instead of passing garbage on.
    bad = '{"summary": "x", "citations": [{"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e"}], "confidence": 2}'  # noqa: E501
    agent = build_agent(config, model=canned_model(bad))
    with pytest.raises(UnexpectedModelBehavior, match="output retries"):
        agent.run_sync("anything", deps=retriever)
