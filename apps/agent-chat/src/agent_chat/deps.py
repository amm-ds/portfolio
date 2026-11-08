"""Chat agent dependencies: the per-run state tools may touch."""

from dataclasses import dataclass, field

from agent_chat.approvals import ApprovalGate
from agent_chat.memory.notebook import NotebookStore
from agent_chat.schemas import SentMessage


@dataclass
class ChatDeps:
    """Threaded through every run as ``RunContext[ChatDeps]``.

    ``approvals`` gates consequential tools; ``memory`` + ``session_id`` scope
    the browser-session notebook; ``sent`` records what the agent posted.
    """

    approvals: ApprovalGate
    memory: NotebookStore | None = None
    session_id: str = "local"
    sent: list[SentMessage] = field(default_factory=list)
