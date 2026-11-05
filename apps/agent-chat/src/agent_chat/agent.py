"""Agent assembly: the one place the model, tools, skills, and budgets meet.

``build_agent`` wires the pydantic-ai ``Agent`` exactly the way an adopter
copies it — instructions, structured ``Answer`` output, named toolsets,
deferred skills from disk, the bound ``retrieve`` tool, per-run ``UsageLimits``,
and bounded model retries. Swap the model via ``models.build_model``; change
the persona via ``BASE_INSTRUCTIONS``; extend via ``toolsets.TOOLSETS`` and
skill folders — nothing else in the file moves.
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset
from pydantic_ai.usage import UsageLimits

from agent_chat.capabilities import load_skills
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.rag.embeddings import Embedder
from agent_chat.rag.store import VectorStore
from agent_chat.rag.tool import build_retrieve_tool
from agent_chat.schemas import Answer
from agent_chat.toolsets import TOOLSETS, core_toolset, messaging_toolset

BASE_INSTRUCTIONS = """\
You are the agent-chat assistant: concise, factual, and honest about limits.

Tool discipline:
- calculator for arithmetic; never do math in your head when a tool can do it.
- clock for anything about the current date or time.
- retrieve for questions answered by ingested knowledge-base documents; cite
  the passages you relied on (source + quote). If retrieval returns nothing,
  say the knowledge base does not cover it — do not answer from memory.
- Skills load on demand: when a task matches a skill's description, call
  load_capability for it, then follow its instructions and use its tools.
  Never answer policy questions from memory when the handbook skill covers them.
- send_message posts to team channels and requires human approval; use it only
  when the user explicitly asks to notify or announce something, and treat a
  denial as final.

Answering rules:
- Answer the question asked; no preamble, no restating, no sign-off.
- Every claim grounded in retrieval or a skill gets a citation.
- Set uncertainty honestly: "high" when you had to guess or the evidence was
  thin, "low" when a tool or cited passage settles it.
- If a request is outside your tools and skills, say plainly what is missing
  instead of inventing a capability or a number.
"""


def build_usage_limits(settings: Settings) -> UsageLimits:
    """Per-run budgets from settings; 0 disables a limit."""
    return UsageLimits(
        request_limit=settings.usage_request_limit or None,
        input_tokens_limit=settings.usage_input_tokens_limit or None,
        output_tokens_limit=settings.usage_output_tokens_limit or None,
    )


def build_agent(
    *,
    model: Model,
    settings: Settings | None = None,
    vector_store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> Agent[ChatDeps, Answer]:
    """Assemble the agent.

    ``vector_store`` + ``embedder`` together attach the ``retrieve`` tool;
    pass neither (default) for an agent without a knowledge base. Skills load
    from ``settings.skills_dir`` (disk folders — see ``capabilities``).
    """
    settings = settings or Settings()
    toolsets: list[AbstractToolset[ChatDeps]] = [core_toolset(), messaging_toolset()]
    if settings.fetch_url_enabled:
        toolsets.append(TOOLSETS["web"]())
    if vector_store is not None and embedder is not None:
        rag_toolset: FunctionToolset[ChatDeps] = FunctionToolset(
            [build_retrieve_tool(vector_store, embedder)], id="rag"
        )
        toolsets.append(rag_toolset)

    return Agent(
        model,
        output_type=Answer,
        instructions=BASE_INSTRUCTIONS,
        deps_type=ChatDeps,
        toolsets=toolsets,
        capabilities=load_skills(settings.skills_dir),
        retries=settings.model_retries,
    )
