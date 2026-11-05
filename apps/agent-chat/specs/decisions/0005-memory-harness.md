# ADR-0005: Harness-style personal memory and bounded history

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

A stored pydantic-ai `Conversation` continues one thread; it does not provide a
bounded, user-scoped fact store that survives new conversations and process
restarts. Replaying every old message or injecting every stored note makes token
cost grow with tenure and mixes durable preferences with transient dialogue.
Pydantic AI Harness separates these concerns: `Memory` is a namespaced notebook
with on-demand search, while history processors bound what a model sees.

The template needs the same separation with only two model tools (`remember`
and `recall`), one file per user, and deterministic offline tests. It also needs
a free default for long conversations; an LLM summary on every turn would add
cost, latency, and another failure mode.

## Decision

**Use the Harness Memory pattern with automatic injection disabled.** A
`FileNotebook` stores one `<user_id>.json` file under
`AGENT_CHAT_MEMORY_DATA_DIR` (default `./agent_chat_memory`). The JSON contains
a schema version and notes with a stable id, concise fact, and UTC timestamp.
Whitespace-normalized exact repeats are idempotent. User ids are validated as
safe filename components and come from server-side deps, never tool arguments.
The API currently accepts `user_id` on `/chat` and defaults it to `local`;
authenticated deployments must derive it from the authenticated principal
instead of trusting the request body.

`remember` appends an explicit durable user fact. `recall` performs case-folded
literal term scoring and returns at most the requested 1–10 matching notes
(default five), best score and newest first. Only those matches enter the tool
result. There is no notebook excerpt, file listing, or whole-store content in
instructions or prompts. Notes remain untrusted user context, not instructions.
This is the equivalent of Harness Memory's `inject_memory=False` policy with a
smaller two-tool surface and a one-file store.

**Trim by default; summarize only on overflow.** A pydantic-ai
`ProcessHistory` capability retains the last
`AGENT_CHAT_HISTORY_MAX_TURNS` user turns (default ten), including each turn's
tool calls/results and the current request. The default processor is synchronous
and makes no model call. Setting `AGENT_CHAT_HISTORY_SUMMARIZE_ENABLED=true`
uses the configured model to summarize only the turns about to be dropped, then
prepends one delimited summary to the unchanged recent window. A summary is not
counted as a user turn, so internal tool steps do not repeatedly summarize.
Tests inject the same scripted fake into the summarizer; CI never uses a network.

The template's whole-`Conversation` store persists the processed, bounded
conversation it will continue from. Applications needing an immutable full
transcript should use pydantic-ai's append-only `ConversationStore` or a separate
audit log; durable personal facts belong in the notebook.

## Consequences

- A second agent process can recall a completed write immediately; a new
  conversation can recall facts written in an old one.
- Prompt size is bounded by recent history plus selected recall results, not by
  the number of notebooks or notes on disk.
- Literal recall is predictable and dependency-free, but it is not semantic
  retrieval. Replace `NotebookStore` with an indexed implementation when fuzzy
  matching is required, preserving tenant scope and result bounds.
- Atomic file replacement prevents partial files. The file backend serializes
  writers within one instance but does not provide cross-process compare-and-swap;
  use a transactional store before allowing concurrent writers for one user.
- Summarization adds one model request only when a request overflows the window.
  It can omit details and spends tokens, so it is opt-in. Trimming can remove
  context either way; `remember` is for facts that must survive that loss.
- Notebook files can contain personal data and model-written prompt injection.
  Do not store secrets, apply retention/access controls, and keep recalled text
  below instruction authority.
