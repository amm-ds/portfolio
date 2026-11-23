"""Agent tests: structured output validation with a test-only FunctionModel."""

import json

import pytest
from portfolio_core.llm import mock_model_for_tests
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from rag_agent.agent import agent_usage_limits, build_agent
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


def test_agent_usage_limits_applies_configured_rails(config: RAGConfig) -> None:

    limits = agent_usage_limits(config)
    assert limits.request_limit == 12
    assert limits.tool_calls_limit == 16
    assert limits.input_tokens_limit == 200_000

    custom = config.model_copy(
        update={
            "agent_request_limit": 3,
            "agent_tool_calls_limit": 5,
            "agent_input_tokens_limit": 9_000,
        }
    )
    limits = agent_usage_limits(custom)
    assert limits.request_limit == 3
    assert limits.tool_calls_limit == 5
    assert limits.input_tokens_limit == 9_000


def test_search_documents_top_k_is_clamped(config: RAGConfig, retriever: Retriever) -> None:
    """A model asking for top_k=50 must reach retrieval clamped to 10."""
    seen: list[int] = []
    original = retriever.search

    def recording_search(query: str, top_k: int | None = None) -> list:
        seen.append(top_k if top_k is not None else -1)
        return original(query, top_k=top_k)

    retriever.search = recording_search  # type: ignore[method-assign]

    calls = {"n": 0}

    def tool_calling_model(messages: list, info: object) -> list:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="search_documents",
                        args={"query": "climate", "top_k": 50},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(CANNED_ANALYSIS_JSON)])

    agent = build_agent(config, model=FunctionModel(tool_calling_model))
    result = agent.run_sync("climate?", deps=retriever)
    assert isinstance(result.output, AnalysisResult)
    assert seen and all(k == 10 for k in seen)


def test_soft_tool_budget_ceiling_blocks_before_hard_rail(
    config: RAGConfig, retriever: Retriever
) -> None:
    """Revision 1: at the soft ceiling search returns [] and read_excerpt returns
    the TOOL BUDGET notice, so the run never hits UsageLimitExceeded."""
    custom = config.model_copy(
        update={"agent_request_limit": 6, "agent_tool_calls_limit": 8}
    )  # soft limits: 3 requests / 4 tool calls
    calls = {"n": 0}
    observations: list[str] = []

    def model_fn(messages: list, info: object) -> ModelResponse:
        calls["n"] += 1
        for message in messages:
            for part in message.parts:
                if part.part_kind == "tool-return":
                    observations.append(str(part.content))
        if calls["n"] <= 3:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="search_documents", args={"query": "climate"})]
            )
        if calls["n"] == 4:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="read_excerpt", args={"citation_id": "x"})]
            )
        return ModelResponse(parts=[TextPart(CANNED_ANALYSIS_JSON)])

    agent = build_agent(custom, model=FunctionModel(model_fn))
    result = agent.run_sync("climate?", deps=retriever, usage_limits=agent_usage_limits(custom))
    assert isinstance(result.output, AnalysisResult)
    assert "[]" in observations  # blocked search_documents
    assert any("TOOL BUDGET REACHED" in o for o in observations)  # blocked read_excerpt
