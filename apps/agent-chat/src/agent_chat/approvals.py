"""Human-in-the-loop approvals for consequential tools.

The agent depends only on the :class:`ApprovalGate` protocol. Evals and local
CLI runs wire :class:`AutoApproval` (always yes); the API wires a registry
that emits ``approval_request`` SSE events and waits for a
``POST /approvals/{id}`` decision, with a timeout that defaults to deny.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ApprovalRequest:
    """What the gate asks the human, and under which id the answer arrives."""

    approval_id: str
    tool: str
    summary: str


class ApprovalGate(Protocol):
    """Ask a human (or test double) whether a consequential action may run.

    Returns ``True`` = approved, ``False`` = denied or timed out. Implementations
    must never raise for a missing answer — default-deny is the contract.
    """

    async def request(self, tool: str, summary: str) -> bool: ...


@dataclass
class AutoApproval:
    """Approve everything. Default outside the API (evals, REPL, scripts)."""

    async def request(self, tool: str, summary: str) -> bool:
        return True


@dataclass
class DenyAll:
    """Deny everything. For refusal/audit paths that must never act."""

    async def request(self, tool: str, summary: str) -> bool:
        return False
