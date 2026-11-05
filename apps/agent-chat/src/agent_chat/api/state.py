"""Application state and the approval hub.

``AppState`` is everything the routes need, built once in ``create_app``.
``ApprovalHub`` is the API-side ``ApprovalGate``: each chat run gets a gate
bound to its own SSE queue (so concurrent chats never cross streams), the hub
tracks pending futures by approval id, and ``POST /approvals/{id}`` resolves
them from any thread/loop via ``call_soon_threadsafe``. Timeout = default deny.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import uuid4

from pydantic_ai import Agent

from agent_chat.api.events import ApprovalRequestEvent, ApprovalResponseEvent
from agent_chat.approvals import ApprovalGate
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.memory import ConversationStore
from agent_chat.rag.embeddings import Embedder
from agent_chat.rag.store import VectorStore
from agent_chat.schemas import Answer


@dataclass
class AppState:
    """Everything the FastAPI routes share; one instance per app."""

    settings: Settings
    agent: Agent[ChatDeps, Answer]
    conversation_store: ConversationStore
    vector_store: VectorStore
    embedder: Embedder
    approval_hub: "ApprovalHub"


EventSink = Callable[[ApprovalRequestEvent | ApprovalResponseEvent], None]


@dataclass
class _PendingApproval:
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[bool]


@dataclass
class ApprovalHub:
    """App-wide registry of in-flight approval requests."""

    timeout_s: float
    _pending: dict[str, _PendingApproval] = field(default_factory=dict)

    def gate(self, sink: EventSink) -> ApprovalGate:
        """An ``ApprovalGate`` for one chat run, emitting into that run's sink."""
        return _SseApprovalGate(hub=self, sink=sink)

    def resolve(self, approval_id: str, approved: bool) -> bool:
        """Answer a pending request (thread-safe). False when unknown/settled."""
        pending = self._pending.get(approval_id)
        if pending is None or pending.future.done():
            return False
        pending.loop.call_soon_threadsafe(pending.future.set_result, approved)
        return True

    def _register(self, approval_id: str, future: asyncio.Future[bool]) -> None:
        self._pending[approval_id] = _PendingApproval(asyncio.get_running_loop(), future)

    def _deregister(self, approval_id: str) -> None:
        self._pending.pop(approval_id, None)


@dataclass
class _SseApprovalGate:
    """Binds the hub's pending registry to one run's event sink."""

    hub: ApprovalHub
    sink: EventSink

    async def request(self, tool: str, summary: str) -> bool:
        approval_id = uuid4().hex[:12]
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.hub._register(approval_id, future)
        self.sink(ApprovalRequestEvent(approval_id=approval_id, tool=tool, summary=summary))
        try:
            approved = await asyncio.wait_for(future, timeout=self.hub.timeout_s)
        except TimeoutError:
            approved = False  # default-deny: no answer in time, action does not run
        finally:
            self.hub._deregister(approval_id)
        self.sink(ApprovalResponseEvent(approval_id=approval_id, approved=approved))
        return approved
