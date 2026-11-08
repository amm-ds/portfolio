# ADR-0006: Anonymous browser-session identity

- **Status:** Accepted
- **Date:** 2026-11-07
- **Amends:** ADR-0005's per-user identity decision

## Context

The first memory implementation accepted `user_id` on `/chat` and defaulted it
to `local`. The browser did not send that field, so every visitor shared one
notebook and one global conversation list. That is unsuitable for a public
showcase. The application does not need accounts, login, or user-management UI,
but it does need predictable memory lifetime and isolation between visitors.

A fully persistent account would add identity and security work without improving
the demonstration. Conversation-only memory would lose useful preferences when
the user starts a new chat. A browser session provides the middle ground: memory
can follow related conversations without becoming a permanent shared profile.

## Decision

Generate a canonical UUID with `crypto.randomUUID()` and store it in
`sessionStorage` under `agent-chat:session-id`. The `HttpChatApi` sends it as
`X-Agent-Chat-Session` on chat, approvals, and conversation list/get/delete.
New conversations and reloads in the same tab reuse it; closing the tab starts
a fresh namespace. `+ new` starts a conversation, not a new memory session.

Require and validate that header at the API boundary. Remove `user_id` from the
public chat body and use `session_id` in `ChatDeps` and the notebook protocol.
The session id never enters model tool arguments.

Scope all user-visible state by the session:

- conversation save/get/list/delete and chat continuation;
- notebook remember/recall;
- pending approval resolution.

Cross-session resources return 404. Pending approvals carry their owning session
in addition to their one-shot id. Conversation stores add a `session_id` column
and index idempotently; old rows remain in the `legacy` namespace instead of
being assigned to a new visitor.

Memory notes accept an optional stable snake_case key. Reusing a key updates
the fact and avoids paraphrase duplicates; exact unkeyed repeats remain
idempotent. Notebook JSON version 2 adds `key` and `updated_at` while version-1
files remain readable.

## Consequences

- Same-tab conversations can recall preferences without account infrastructure.
- Different tabs and browsers cannot accidentally list, continue, delete, or
  approve one another's work through normal UI behavior.
- The header is an isolation label, **not authentication**. Anyone who can choose
  headers can choose a session id, so production deployments must derive tenant
  identity from an authenticated principal instead.
- Closing a tab starts a new namespace but does not securely erase old notebook
  files or conversation rows. Retention cleanup, access controls, and backup
  policy remain adopter responsibilities.
- File notebooks still serialize writes only within one store instance. Use a
  transactional implementation for concurrent writers.
- Additive migrations preserve old data without making it visible to new
  sessions. A deliberate migration/export would be needed to reclaim legacy rows.
