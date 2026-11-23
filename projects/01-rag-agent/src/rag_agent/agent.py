"""The agentic layer: a pydantic-ai agent whose only evidence is retrieval.

The agent's dependencies are a :class:`~rag_agent.index.Retriever`; its two
tools (``search_documents`` / ``read_excerpt``) are the *only* way it can
access the corpus, and its output is the structured :class:`AnalysisResult` —
a grounded summary with per-claim citations and a calibrated confidence.

Provider behaviour follows ADR-0004 (amended wave 10): a live model comes from
the platform factory — env-configured OpenAI-compatible endpoint first, local
Ollama (platform default ``qwen3.6:35b-a3b-q4_K_M``) second. There is deliberately no runtime mock;
when neither provider is available, :class:`portfolio_core.llm.LLMProviderUnavailableError`
raises with setup guidance, and ``chat``/``evaluate`` surface that message.
"""

from typing import Any

from portfolio_core.llm import build_model
from portfolio_core.llm_budget import budget_limits
from portfolio_core.logging import get_logger
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.tools import RunContext

from rag_agent.config import RAGConfig
from rag_agent.index import Retriever
from rag_agent.provider import model_settings_for_provider
from rag_agent.schemas import AnalysisResult, Citation

logger = get_logger(__name__)


def agent_usage_limits(config: RAGConfig) -> Any:
    """UsageLimits for one evaluated question: platform budget limits plus the
    bounded agent-loop rails (ported from agent-loop-bounds-2026-11-20).

    Local Ollama has no hosted budget limits; the rails still apply so a
    runaway tool loop stops deterministically in every environment.
    """
    from pydantic_ai.usage import UsageLimits

    limits = budget_limits()
    if limits is None:
        return UsageLimits(
            request_limit=config.agent_request_limit,
            tool_calls_limit=config.agent_tool_calls_limit,
            input_tokens_limit=config.agent_input_tokens_limit,
        )
    import dataclasses

    return dataclasses.replace(
        limits,
        request_limit=config.agent_request_limit,
        tool_calls_limit=config.agent_tool_calls_limit,
        input_tokens_limit=config.agent_input_tokens_limit,
    )


SYSTEM_PROMPT = """You are a meticulous research assistant over a curated Wikipedia corpus.

Rules you must always follow:
1. Answer ONLY from evidence returned by search_documents / read_excerpt.
   Never use outside knowledge.
2. Every factual claim in `summary` must be supported by at least one entry in
   `citations`.
3. Always call search_documents before answering; call read_excerpt when an
   excerpt is too short to verify a claim.
4. Set `confidence` to 1.0 only if the retrieved evidence fully answers the
   question; lower it when evidence is partial or contradictory.
5. Do at most 2\u20133 search_documents calls per question. If the returned passages
   do not contain the specific subject, entity, event, or fact asked about,
   the topic is absent from the corpus: immediately stop calling tools, state
   in `summary` that no relevant evidence was found, set `confidence` below 0.3,
   and leave `citations` AND `claims` EMPTY — never keep reformulating searches
   or cite passages you judge irrelevant just to satisfy the schema. An honest
   refusal cites nothing.
6. Lead with the direct answer to the question; omit generic background and
   do not add facts the user did not request.
7. A citation supports only claims present in that exact excerpt. Never attach
   a topically related citation to an unsupported claim.
8. R6: `claims` must list every factual sentence of `summary` in order, each
   with `citation_chunk_ids` and one or more `spans`. A span is a VERBATIM
   substring of that chunk's text — copy it exactly, never paraphrase it.
9. Never state a number, date, or duration that is not present verbatim in a
   span. If a value must be computed from the evidence, do not state it —
   abstain on that claim instead. (Derived claims are not accepted.)
10. Multi-hop answers: cite every article the claim combines, with one span
   per leg.
"""


def build_agent(config: RAGConfig, model: Model | None = None) -> Agent[Retriever, AnalysisResult]:
    """Build the analysis agent; ``model`` override is for tests (FunctionModel).

    ``RAG_NATIVE_OUTPUT=1`` switches the final answer to grammar-constrained
    JSON (pydantic-ai NativeOutput) instead of tool-call output — the Ollama
    /v1 endpoint's tool protocol returns empty responses for some local
    models (qwen2.5:3b; the R7 judge-calibration finding), so local
    generation runs use the native path.
    """
    import os

    from pydantic_ai import NativeOutput

    resolved_model = model if model is not None else build_model()
    output_type: Any = (
        NativeOutput(AnalysisResult)
        if os.environ.get("RAG_NATIVE_OUTPUT", "").strip() in {"1", "true"}
        else AnalysisResult
    )
    agent = Agent(
        resolved_model,
        output_type=output_type,
        deps_type=Retriever,
        system_prompt=SYSTEM_PROMPT,
        model_settings=model_settings_for_provider(),
    )

    @agent.tool
    async def search_documents(
        ctx: RunContext[Retriever], query: str, top_k: int = 5
    ) -> list[Citation]:
        """Search the corpus for passages relevant to ``query``; returns ranked citations.

        ``top_k`` is clamped to 1..10 (agent-loop-bounds-2026-11-20): unbounded
        values blow up the reranker candidate pool and the answer context.
        """
        k = max(1, min(top_k, 10))
        return ctx.deps.search(query, top_k=k)

    @agent.tool
    async def read_excerpt(ctx: RunContext[Retriever], citation_id: str) -> str:
        """Read the full text of a previously retrieved chunk by its chunk_id."""
        chunk = ctx.deps.get_chunk(citation_id)
        if chunk is None:
            return f"chunk {citation_id!r} not found in the index"
        return chunk.text

    return agent
