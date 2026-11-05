"""The retrieve tool: the agent's search interface over the vector store.

Bound to a store + embedder by :func:`build_retrieve_tool`; pure functions
with closures keep the agent assembly declarative (the model-facing schema
comes from the docstring, per the repo's tool convention).
"""

from collections.abc import Awaitable, Callable

from agent_chat.rag.embeddings import Embedder
from agent_chat.rag.store import VectorStore


def build_retrieve_tool(
    store: VectorStore, embedder: Embedder
) -> Callable[..., Awaitable[list[str]]]:
    """Create the ``retrieve`` tool bound to ``store`` and ``embedder``."""

    async def retrieve(query: str, top_k: int = 4) -> list[str]:
        """Search the knowledge base for passages relevant to a question.

        Use for questions about ingested documents (runbooks, policies, notes)
        — never for arithmetic (use calculator), time (use clock), or anything
        a skill's own search tool covers.

        Args:
            query: Natural-language question or search terms.
            top_k: Maximum number of passages to return (1-8).

        Returns:
            Passages "source#chunk (score): text", best match first.
        """
        k = max(1, min(top_k, 8))
        query_vector = (await embedder.embed([query]))[0]
        hits = await store.search(query_vector, top_k=k)
        return [f"{h.source}#{h.chunk_index} (score {h.score:.2f}): {h.content}" for h in hits]

    return retrieve
