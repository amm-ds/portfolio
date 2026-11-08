"""Model-facing notebook tools. Identity comes from deps, never model args."""

from pydantic_ai import RunContext

from agent_chat.deps import ChatDeps


def _unavailable() -> str:
    return "Memory is unavailable: no notebook was configured for this run."


async def remember(ctx: RunContext[ChatDeps], fact: str, key: str | None = None) -> str:
    """Store a fact the user asks you to remember in this browser session.

    Args:
        fact: One concise user preference, identity detail, or explicit decision.
        key: Optional stable snake_case identity such as preferred_cloud. Reuse
            the same key to update a preference without creating a duplicate.

    Returns:
        Confirmation with the complete stored fact, or why memory is unavailable.
    """
    if ctx.deps.memory is None:
        return _unavailable()
    note = await ctx.deps.memory.remember(ctx.deps.session_id, fact, key=key)
    label = note.key or "fact"
    return f"Remembered {label}: {note.fact}"


async def recall(ctx: RunContext[ChatDeps], query: str, limit: int = 5) -> str:
    """Retrieve only stored notes relevant to the current user question.

    Use only when the user asks about a personal preference or identity detail
    they explicitly stored in an earlier run. Never use it for prices, business
    records, inventory, current data, available capabilities, or to fulfill a new
    task; those are outside the notebook's contract.

    Args:
        query: Keywords describing the fact to find.
        limit: Maximum notes to return, from 1 to 10 (default 5).

    Returns:
        A bounded list of matching notes, never the complete notebook.
    """
    if ctx.deps.memory is None:
        return _unavailable()
    notes = await ctx.deps.memory.recall(ctx.deps.session_id, query, limit=limit)
    if not notes:
        return "No relevant stored notes found."
    return "Recalled notes:\n" + "\n".join(f"- [{note.id}] {note.fact}" for note in notes)
