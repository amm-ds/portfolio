"""Agent tests: structured output validation with a test-only FunctionModel."""

import json

import pytest
from portfolio_core.llm import mock_model_for_tests
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.function import FunctionModel
from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig
from rag_agent.index import Retriever
from rag_agent.schemas import AnalysisResult

CANNED_ANALYSIS_JSON = json.dumps(
    {
        "summary": "Test-only canned answer.",
        "citations": [
            {
                "chunk_id": "climate-000#c000",
                "article_id": "climate-000",
                "title": "Test citation",
                "excerpt": "Deterministic test excerpt.",
                "score": 1.0,
            }
        ],
        "confidence": 0.5,
    }
)


def canned_model(response: str = CANNED_ANALYSIS_JSON) -> FunctionModel:
    return mock_model_for_tests(response)


def test_agent_output_is_validated_analysis_result(config: RAGConfig, retriever: Retriever) -> None:
    agent = build_agent(config, model=canned_model())
    result = agent.run_sync("what is photosynthesis?", deps=retriever)
    assert isinstance(result.output, AnalysisResult)
    assert result.output.confidence == 0.5
    assert len(result.output.citations) == 1
    assert result.output.citations[0].chunk_id == "climate-000#c000"


def test_agent_rejects_invalid_canned_output(config: RAGConfig, retriever: Retriever) -> None:
    # confidence=2.0 violates the 0..1 bound of AnalysisResult: the run must fail loudly.
    bad = json.dumps(
        {
            "summary": "x",
            "citations": [{"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e"}],
            "confidence": 2,
        }
    )
    agent = build_agent(config, model=canned_model(bad))
    with pytest.raises(UnexpectedModelBehavior, match="output retries"):
        agent.run_sync("anything", deps=retriever)
