"""Chat agent dependencies: the per-run state tools may touch."""

from dataclasses import dataclass, field

from agent_chat.approvals import ApprovalGate
from agent_chat.schemas import SentMessage


@dataclass
class ChatDeps:
    """Threaded through every run as ``RunContext[ChatDeps]``.

    ``approvals`` gates consequential tools (``send_message``); ``sent`` records
    what the agent actually posted, so tests and audits can assert on it.
    """

    approvals: ApprovalGate
    sent: list[SentMessage] = field(default_factory=list)
