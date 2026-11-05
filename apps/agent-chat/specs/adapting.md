# agent-chat — Adapting the template

The copy-out guide. Each recipe names the file(s) to touch and nothing else;
the seams exist so the rest of the code stays untouched. Run the ship
checklist at the bottom before you call it yours.

## 1. Give the agent your identity

**File: `src/agent_chat/agent.py` — the `BASE_INSTRUCTIONS` string.**

This is the first edit every adopter makes: who the agent is, what it may do,
how it answers. Keep the tool-discipline shape (which tool owns which job,
what to do when retrieval is empty, how to set `uncertainty`) and swap the
domain. Pair it with the output shape in `src/agent_chat/schemas.py`
(`Answer.text` / `citations` / `uncertainty`) — e.g. add a `language` field
or a required `audience` and the instructions that mention it.

## 2. Add a tool

1. Write a typed function in `src/agent_chat/tools/`. The **docstring is the
   model-facing schema** — prose plus `Args:`/`Returns:`; the typed signature
   becomes the argument schema. Registration validates at import time: no
   docstring or a private name fails fast (`tools/base.py::validate_tool`).
2. Register it in `src/agent_chat/toolsets/__init__.py` — add it to an
   existing group (`core` is always on; `web` is opt-in network; `messaging`
   is for tools behind the approval gate) or add a builder and one
   `TOOLSETS["<name>"] = <builder>` line and attach it in `build_agent`.

```python
# src/agent_chat/tools/ticket.py
async def create_ticket(ctx: RunContext[ChatDeps], subject: str, body: str) -> str:
    """Open a support ticket in the tracker. CONSEQUENTIAL: requires human approval.

    Use only when the user explicitly asks to file or escalate a ticket.

    Args:
        subject: One-line summary, e.g. "Refund request #1042".
        body: The full ticket description.

    Returns:
        The created ticket id, or a note that it was not created.
    """
    summary = f"create ticket {subject!r}"
    if not await ctx.deps.approvals.request("create_ticket", summary):
        return "Ticket NOT created: denied by operator."
    ...
```

If the tool acts on the world (creates, sends, deletes, pays), route it
through `ctx.deps.approvals` like `send_message` does — the API, evals, and
audit paths pick it up with no further wiring.

## 3. Add a skill

**A folder, nothing else:**

```
src/agent_chat/skills/<name>/SKILL.md        # instructions; first prose paragraph
                                             # = the description the model sees
src/agent_chat/skills/<name>/resources/*.md  # optional reference documents
```

A folder with `resources/` automatically gets a deterministic
`search_<name>` tool; a skill needing a bespoke tool (like `summarize`'s
`summarize_text`) adds one line in `capabilities/loader.py`'s
`EXTRA_TOOL_BUILDERS`. Skills load on demand — the model sees only the
description until it calls `load_capability("<name>")`. If your documents
need semantic rather than keyword search, put them in the vector store
instead and let the `retrieve` tool serve them.

## 4. Swap the model provider

Configuration first: `AGENT_CHAT_PROVIDER=hosted` plus
`HOSTED_BASE_URL` / `HOSTED_API_KEY` / `HOSTED_MODEL`. Code only when the
provider is not OpenAI-compatible: add a branch in
`src/agent_chat/models.py`. Set `*_FALLBACK_MODEL` to chain a failover that
triggers on provider API errors (see `specs/decisions/0001`). The agent,
tools, and API never change.

## 5. Swap the embedder

Implement the two-member protocol in `src/agent_chat/rag/embeddings.py`
(`dim: int` property + `async embed(texts)`), register it in
`build_embedder`, set `AGENT_CHAT_EMBEDDER`. The dimension must match the
store's `VECTOR(dim)` column — so after any embedder change: clear
`rag_chunks` and re-ingest. Hosted embedding services work the same way
(batch the `embed` calls; keep the protocol).

## 6. Add persistent user memory

The default is already wired: `remember` writes an explicit user fact and
`recall` retrieves only relevant notes in a later run or process. Set
`AGENT_CHAT_MEMORY_DATA_DIR` to durable storage. Notes live one user per file;
no notebook content is automatically injected. Keep `remember` limited to facts
the user explicitly asks to store, and treat recalled text as untrusted context.

For a real multi-user deployment, replace the request's default `user_id="local"`
with the authenticated principal in `api/routes_chat.py`; do not accept tenant
identity from model arguments. To change storage or ranking, implement
`NotebookStore` (`remember` + bounded `recall`) in `memory/notebook.py` or a new
adapter, then pass it as `create_app(notebook=...)`. Preserve user isolation and
result limits. An indexed/semantic backend belongs behind this seam, not in the
model tool. The file implementation is durable across restarts but is not a
cross-process compare-and-swap store; use transactions for concurrent writers.

Tune conversation context independently: `AGENT_CHAT_HISTORY_MAX_TURNS` sets the
free sliding window (default ten). `AGENT_CHAT_HISTORY_SUMMARIZE_ENABLED=true`
adds one summarizer request only when history overflows. Keep it off when cost
and determinism matter more than retaining compressed context. The template
persists the processed bounded Conversation; add an append-only transcript if
your audit requirements include trimmed turns. Add a fake-model eval like
`memory-recall-second-turn` for every new memory behavior.

## 7. Restyle the web UI

**File: `web/src/styles.css` — the `:root` variables.** Every color, radius,
and font flows from them; restyling is overriding the block, not hunting
selectors:

```css
:root {
  --bg: #0b1020;            /* page background            */
  --surface: #141b31;       /* sidebar, cards             */
  --surface-hover: #1c2544; /* hover states               */
  --border: #2a3358;        /* hairlines                  */
  --accent: #7aa2ff;        /* primary actions, focus ring*/
  --secondary: #bb9af7;     /* secondary highlights       */
  --text: #dce2f7;          /* body text                  */
  --muted: #8b93b8;         /* timestamps, meta           */
  --danger: #f7768e;        /* errors, deny button        */
  --ok: #9ece6a;            /* success, approve button    */
  --accent-glow: rgba(122, 162, 255, 0.25);
  --radius: 10px;
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

Set `color-scheme: light` alongside light `--bg`/`--text` values for a light
theme. The chat client decodes the backend's SSE schema
(`web/src/lib/chat/events.ts` mirrors `src/agent_chat/api/events.py`) —
restyling does not touch it.

## Ship checklist

- [ ] `uv run pytest -q` — 95 tests green (all offline)
- [ ] `uv run ruff check . && uv run ruff format --check .` and `uv run mypy src tests`
- [ ] `uv run python -m agent_chat.evals.runner` (fake) and
      `uv run python -m agent_chat.evals.runner --model real`; read
      `reports/evals.md` — your instructions/tool changes should not regress
      the refusal and citation graders
- [ ] New domain tools that act on the world go through the approval gate
- [ ] `docker compose up --build`, ingest your own `docs/`, and click through
      a chat plus one approval in the web UI
- [ ] `AGENT_CHAT_API_KEY` set for anything beyond localhost; notebook `user_id`
      derived from the authenticated principal rather than the request body
- [ ] `AGENT_CHAT_EMBEDDER=minilm` (with re-ingest) for semantic retrieval in
      real deployments; `hashing` is for CI and first boots only
- [ ] Your identity in `BASE_INSTRUCTIONS` and your domain limits written
      into it (what the agent must refuse, what it must escalate)
- [ ] If your changes are architectural, record them as ADRs next to
      `specs/decisions/`
