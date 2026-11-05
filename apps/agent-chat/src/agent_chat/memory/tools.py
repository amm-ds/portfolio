"""Model-facing notebook tools. Identity comes from deps, never model args."""

from pydantic_ai import RunContext

from agent_chat.deps import ChatDeps


def _unavailable() -> str:
    return "Memory is unavailable: no notebook was configured for this run."


async def remember(ctx: RunContext[ChatDeps], fact: str) -> str:
    """Store a durable fact the user asks you to remember across conversations.

    Args:
        fact: One concise user preference, identity detail, or explicit decision.

    Returns:
        Confirmation with the stored note, or why memory is unavailable.
    """
    if ctx.deps.memory is None:
        return _unavailable()
    note = await ctx.deps.memory.remember(ctx.deps.user_id, fact)
    return f"Remembered note {note.id}: {note.fact}"


async def recall(ctx: RunContext[ChatDeps], query: str, limit: int = 5) -> str:
    """Retrieve only stored notes relevant to the current user question.

    Use when the user asks about a preference or fact from an earlier run.

    Args:
        query: Keywords describing the fact to find.
        limit: Maximum notes to return, from 1 to 10 (default 5).

    Returns:
        A bounded list of matching notes, never the complete notebook.
    """
    if ctx.deps.memory is None:
        return _unavailable()
    notes = await ctx.deps.memory.recall(ctx.deps.user_id, query, limit=limit)
    if not notes:
        return "No relevant stored notes found."
    return "Recalled notes:\n" + "\n".join(f"- [{note.id}] {note.fact}" for note in notes)
