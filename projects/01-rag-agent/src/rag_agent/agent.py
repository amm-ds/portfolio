"""The agentic layer: a pydantic-ai agent whose only evidence is retrieval.

The agent's dependencies are a :class:`~rag_agent.index.Retriever`; its two
tools (``search_documents`` / ``read_excerpt``) are the *only* way it can
access the corpus, and its output is the structured :class:`AnalysisResult` —
a grounded summary with per-claim citations and a calibrated confidence.

Provider behaviour follows ADR-0004 (amended wave 10): a live model comes from
the platform factory — env-configured OpenAI-compatible endpoint first, local
Ollama (default ``qwen3:32b``) second. There is deliberately no runtime mock;
when neither provider is available, :class:`portfolio_core.llm.LLMProviderUnavailableError`
raises with setup guidance, and ``chat``/``evaluate`` surface that message.
"""

from portfolio_core.llm import build_model
from portfolio_core.logging import get_logger
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.tools import RunContext

from rag_agent.config import RAGConfig
from rag_agent.index import Retriever
from rag_agent.provider import no_think_model_settings
from rag_agent.schemas import AnalysisResult, Citation

logger = get_logger(__name__)

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
5. If retrieval yields no relevant evidence, say so in `summary`, cite the
   closest passages found, and set confidence below 0.3.
"""


def build_agent(config: RAGConfig, model: Model | None = None) -> Agent[Retriever, AnalysisResult]:
    """Build the analysis agent; ``model`` override is for tests (FunctionModel)."""
    resolved_model = model if model is not None else build_model()
    agent = Agent(
        resolved_model,
        output_type=AnalysisResult,
        deps_type=Retriever,
        system_prompt=SYSTEM_PROMPT,
        model_settings=no_think_model_settings(),
    )

    @agent.tool
    async def search_documents(
        ctx: RunContext[Retriever], query: str, top_k: int = 5
    ) -> list[Citation]:
        """Search the corpus for passages relevant to ``query``; returns ranked citations."""
        return ctx.deps.search(query, top_k=top_k)

    @agent.tool
    async def read_excerpt(ctx: RunContext[Retriever], citation_id: str) -> str:
        """Read the full text of a previously retrieved chunk by its chunk_id."""
        chunk = ctx.deps.get_chunk(citation_id)
        if chunk is None:
            return f"chunk {citation_id!r} not found in the index"
        return chunk.text

    return agent
