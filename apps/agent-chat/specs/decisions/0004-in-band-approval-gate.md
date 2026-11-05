# ADR-0004: In-band approval gate with default-deny

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

Consequential tools — anything that acts on the world outside the chat —
need a human decision before they run. The template's demo tool is
`send_message`; adopters replace it with their own (tickets, payments,
deploys) behind the same seam. The design questions were where the question
reaches the human, and what happens when the answer never arrives. An
out-of-band channel (email, chatOps) is operationally heavy for a template and
complicates the demo; an approve-by-default timeout is not acceptable for
side-effecting actions.

## Decision

An in-band gate over the same SSE stream, default-deny on any uncertainty:

- The agent depends only on the `ApprovalGate` protocol
  (`async request(tool, summary) -> bool`). Tools call it before acting; the
  template's `send_message` discards the message on `False`.
- **In-band transport.** The API wires an `ApprovalHub`: each chat run gets a
  gate bound to its own SSE queue. A request mints an id, emits
  `approval_request` on the run's stream, and parks on a future. The human
  answers via `POST /approvals/{id}`; the hub settles the future thread-safely
  and the gate emits `approval_response` on the same stream. One stream drives
  the whole interaction, so the UI renders the pending card where the
  conversation already lives.
- **Default-deny.** `asyncio.wait_for` with `AGENT_CHAT_APPROVAL_TIMEOUT_S`
  (default 120 s); timeout resolves to denied. Implementations must never
  raise for a missing answer, and `resolve()` returns false for unknown or
  already-settled ids (a 404 to the caller). There is no approve-by-default
  path anywhere.
- **Test doubles ship in the package.** `AutoApproval` (always yes — evals,
  REPL, scripts) and `DenyAll` (refusal/audit paths) implement the same
  protocol, which is why the 12-case eval suite can grade the approval flow
  deterministically.
- **Concurrency is isolated by construction.** The gate is per run and bound
  to that run's queue, so two chats awaiting approval at once never see each
  other's requests.

**Upgrade path.** pydantic-ai's `ApprovalRequiredToolset` gives native
approval flows once the version pinned by the template supports them
stably. The migration is local by design: implement the toolset's transport
against the same `POST /approvals/{id}` endpoint, swap it in `build_agent`
where the gate is wired today, and keep the `ApprovalGate` protocol for
non-API surfaces (evals, scripts) that have no HTTP request to ride on.

## Consequences

- The approval UX comes free with any client that can render the stream and
  POST a decision; no webhook infrastructure, no out-of-band state.
- A lost SSE connection means the run is cancelled with it — the action never
  fires, which is the safe direction.
- The 120 s default is a product choice, not a safety mechanism: the safety
  mechanism is that *no* answer and *no* connection both land on deny.
- Approvals are visible but not durable: the request/response events are on
  the stream; the durable record of what the agent actually did is the
  `SentMessage` list in `ChatDeps` (and the persisted conversation). Adopters
  who need an audit trail of pending decisions should log at the hub.
