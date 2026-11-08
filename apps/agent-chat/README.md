# agent-chat

A production-grade, **lift-out-able** chatbot-agent template: one generic,
modular agent you copy out of this repo and adapt. Built on pydantic-ai v2 +
FastAPI + Postgres/pgvector, with deterministic tests (a scripted fake model —
no network, no API keys) and a real eval suite behind the same graders.

```text
src/agent_chat/
├── config.py         # every knob: providers, stores, history, budgets, embedder
├── models.py         # provider factory: Ollama default, hosted OpenAI-compatible, fallback chain
├── agent.py          # assembly: instructions, Answer output, toolsets, skills, history
├── approvals.py      # the ApprovalGate protocol (HITL seam for consequential tools)
├── deps.py           # ChatDeps: approvals, user-scoped notebook, per-run audit state
├── schemas.py        # Answer / Citation / SentMessage — the typed contracts
├── testing.py        # scripted fake model for tests and CI evals
├── tools/            # calculator, clock, fetch_url (opt-in network), send_message (HITL demo)
├── toolsets/         # named groups: core / web / messaging / memory
├── capabilities/     # skills loaded from disk folders, progressive disclosure
├── skills/           # handbook/ and summarize/ — adding a skill = adding a folder
├── rag/              # chunking, Embedder protocol, pgvector store + SQLite fallback, ingest CLI
├── memory/           # Session conversations + notebook + history processors
├── evals/            # 16-case pydantic-evals suite + markdown reports
└── api/              # FastAPI: SSE chat, approvals, conversations CRUD, ingest, health
infra/                # docker-compose (Postgres 16 + pgvector), multi-stage Dockerfile
tests/                # unit + API suites, all against the fake model and SQLite
```

## Prerequisites

- Python 3.12.9 and [uv](https://docs.astral.sh/uv/).
- Node.js 22+ and npm for the React UI.
- Either Docker with the Compose plugin, or SQLite for docker-free local storage.
- Ollama with `ollama pull qwen3:8b`, or an OpenAI-compatible hosted provider.
  The model is never downloaded by the app; tests need neither Ollama nor a key.

Run all backend commands from `apps/agent-chat/`, which is its own uv workspace.

## Quickstart (docker)

```bash
cd apps/agent-chat/infra
docker compose up --build                        # api on :8000, Postgres 16 + pgvector behind it
docker compose --profile tools run --rm ingest   # one-shot: ingest ./docs into the vector store

cd ../web
npm ci
npm run dev                                     # UI on http://localhost:4322
```

The compose stack uses the dependency-free hashing embedder so it runs without
downloading torch. For semantic embeddings, install the extra and switch the
env (see "How to adapt it" and `specs/operations.md`). On stock Linux Docker,
add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `api` service.

## Quickstart (local, no docker)

```bash
cd apps/agent-chat
uv sync                                         # own venv; Python 3.12.9
export AGENT_CHAT_EMBEDDER=hashing              # or: uv sync --extra embeddings
uv run uvicorn --factory agent_chat.api.app:create_app --port 8000

cd web
npm ci
npm run dev                                     # UI on http://localhost:4322
```

Defaults target a local Ollama (`qwen3:8b`) with a SQLite file for storage.
`VITE_API_PROXY_TARGET` changes the API origin used by the Vite dev proxy.
For a zero-backend UI smoke run, use `VITE_MOCK=1 npm run dev`; its scripted
transport exercises streaming and approval but makes no model or memory claims.

Hosted OpenAI-compatible providers work too; the fallback model is optional:

```bash
export AGENT_CHAT_PROVIDER=hosted \
       AGENT_CHAT_HOSTED_BASE_URL=https://api.example.com/v1 \
       AGENT_CHAT_HOSTED_API_KEY=... \
       AGENT_CHAT_HOSTED_MODEL=... \
       AGENT_CHAT_HOSTED_FALLBACK_MODEL=...
```

For Kimi, use the OpenAI-compatible coding endpoint and a local secret:

```bash
export AGENT_CHAT_PROVIDER=kimi \
       AGENT_CHAT_KIMI_BASE_URL=https://api.kimi.com/coding/v1 \
       AGENT_CHAT_KIMI_API_KEY=... \
       AGENT_CHAT_KIMI_MODEL=k3-256k
```

Other available model ids include `kimi-for-coding` and `k3.1-pro`, subject to
membership access. This showcase uses a Kimi Code membership key; adopters
building their own product should evaluate the pay-as-you-go Kimi Platform
(`https://api.moonshot.ai/v1`) through the generic hosted provider instead.

Never commit `.env` or expose a privileged provider key through `VITE_*`.

## The API

- `POST /chat` — body `{"message": "...", "conversation_id": "..."}` with
  `X-Agent-Chat-Session: <uuid>`. The browser creates and stores this anonymous
  session id automatically; do not put it in the message body or tool arguments.
  The route streams SSE events: `text_delta`, `tool_call_start`/`tool_call_end`,
  `approval_request`/`approval_response` (the consequential `send_message`
  tool waits for a human; timeout = deny), `done` (typed `Answer` + usage +
  conversation id), `error`. Answer with `POST /approvals/{id}`, the same session
  header, and body `{"approved": true}`.
- `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}` —
  all require the session header and expose only that session's conversations.
- `POST /ingest` — body `{"paths": ["docs/"]}`; chunk + embed + index
- `GET /health`, `GET /ready` — liveness with configured provider/model and
  readiness store probes
- Every response carries `X-Request-ID`; errors are a structured envelope:
  `{"error": {"code", "message", "request_id"}}`. Set `AGENT_CHAT_API_KEY`
  to require an `X-API-Key` header on chat/mutations.

## Deployment topology

Build the SPA with `cd apps/agent-chat/web && npm ci && npm run build` and serve
`web/dist` as static files. Put a TLS reverse proxy in front of the static UI
and the FastAPI service; keep Postgres and the API on a private network. Proxy
`/chat`, `/conversations`, `/approvals`, `/ingest`, `/health`, and `/ready` to
the API. For the SSE route, disable response buffering and set a read timeout
that covers provider latency and the human approval window:

```nginx
location /chat {
    proxy_pass http://agent-chat-api:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Request-ID $request_id;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 600s;
}
```

Production configuration belongs in the host's protected environment or secret
manager: `AGENT_CHAT_DATABASE_URL`, `AGENT_CHAT_API_KEY`, provider credentials,
model/budget limits, and `AGENT_CHAT_EXECUTOR_WORKERS`. Do not put privileged
values in `VITE_*` variables — they are compiled into public browser assets.
A public SPA needs an authenticated gateway that injects API credentials;
`VITE_API_KEY` is suitable only for a trusted local/demo client. The anonymous
session header isolates demo state but is not authentication. A production
gateway must derive tenant identity from its authenticated principal and apply
retention cleanup to old notebooks and conversation rows.

Before rollout, ingest with the same embedder configured on the API, wait for
`/ready`, run the offline suite plus `--model real`, and test one approval end
to end through the proxy. Keep the previous image and a Postgres backup for
rollback; `specs/operations.md` covers bring-up, backup, restore, and failures.

## Persistent memory without prompt bloat

`memory/notebook.py` follows pydantic-ai Harness Memory's on-demand pattern.
The browser generates one UUID in `sessionStorage` under `agent-chat:session-id`.
New conversations and reloads in the same tab share that namespace; closing the
tab starts a fresh one. No login or user-management UI is involved. Conversations,
approvals, and notebooks from other sessions are inaccessible.

There is one `<session_id>.json` notebook per session under
`AGENT_CHAT_MEMORY_DATA_DIR` (default `./agent_chat_memory`). Each versioned file
contains notes with a stable id, fact, UTC timestamps, and an optional stable
snake_case key. Reusing a key such as `preferred_cloud` updates the fact instead
of appending a paraphrase duplicate; exact unkeyed repeats remain idempotent.
Version-1 notebooks remain readable. `recall` ranks literal matches over key and
fact, returning five notes by default (hard bound ten). The session id comes from
`ChatDeps`, never model arguments.

There is deliberately **no automatic notebook injection**: instructions describe
when to call the tools, and only the selected recall results enter the model's
context. Recall is lexical, not semantic; implement the `NotebookStore` protocol
to swap in indexed retrieval without changing the agent tools. The session header
is not authentication or secure deletion; production deployments need an
authenticated principal and retention cleanup for old files and rows.

Conversation history is bounded separately in `memory/history.py`. The default
`ProcessHistory` keeps the last `AGENT_CHAT_HISTORY_MAX_TURNS=10` user turns,
including tool legs, with no model call. Set
`AGENT_CHAT_HISTORY_SUMMARIZE_ENABLED=true` to summarize only overflow turns
with the configured model; the recent window remains verbatim. The template's
whole-Conversation store persists this bounded result. Keep durable session facts
in the notebook, and add an append-only store if you need a full audit transcript.
See `specs/decisions/0005-memory-harness.md` and
`specs/decisions/0006-browser-session-identity.md` for the policy and its limits.

## How to adapt it

**What do I edit first? `src/agent_chat/agent.py` — the `BASE_INSTRUCTIONS`
string.** It is the agent's identity and ground rules; everything else plugs
in around it.

Then, in order of how often you'll touch them:

1. **Skills** — add a folder under `src/agent_chat/skills/<name>/SKILL.md`
   (first paragraph = the description the model sees). Folders with a
   `resources/` directory automatically get a `search_<name>` tool. Skill
   tools and instructions stay hidden until the model loads them
   (progressive disclosure) — nothing else to wire.
2. **Tools** — add a typed function in `src/agent_chat/tools/` (docstring =
   the model-facing schema) and register it in `toolsets/TOOLSETS`.
3. **Persona rules / output shape** — `schemas.py` (`Answer`) and
   `agent.py` (`BASE_INSTRUCTIONS`).
4. **Budgets and execution** — `config.py` usage limits (per-run
   requests/tokens), `approval_timeout_s`, `model_retries`, and
   `executor_workers`. The API owns one bounded `UseThreadExecutor` capability
   and closes it on shutdown; it covers synchronous agent callbacks, not the
   explicit `asyncio.to_thread` calls in storage code.
5. **Providers** — `models.py` only; the agent never knows.
6. **Embeddings** — `rag/embeddings.py` implements the `Embedder` protocol;
   MiniLM is the default, the hashing embedder needs no dependencies.
7. **Memory** — replace `NotebookStore` for semantic/shared storage, tune the
   history window in `config.py`, or extend notes with provenance. Keep recall
   bounded and never inject the whole notebook. Full recipe: `specs/adapting.md`.

## Evals

```bash
uv run pytest -q                            # everything, fully offline
uv run python -m agent_chat.evals.runner    # suite vs the scripted fake model
uv run python -m agent_chat.evals.runner --model real   # vs the configured model
```

The 16 cases grade answer correctness, exact tool choice, citation behavior,
refusal probes, approval flow, complete memory acknowledgement, and recall in a
fresh run — with deterministic graders (no LLM in the judge). CI runs them
against the fake; `--model real` grades your actual deployment with the same
graders. Reports include the provider and primary model; use `--out` to keep
separate model reports.

## Tests

`tests/` covers tools, skills, RAG (SQLite-backed), session-scoped conversations
and approvals, notebook persistence and recall bounds, history trim/summarize,
the agent, the API, and an eval-suite smoke run — all deterministic.

```bash
uv run pytest -q                                  # backend, fully offline
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests                             # strict

cd web
npm ci && npm test && npm run lint && npm run build
npm run test:e2e                                # mock transport on :4399
```

With the API and UI running, `node web/scripts/record-demo.mjs` refreshes the
calculator/approval/memory screenshots and compressed WebM + MP4 walkthroughs
(requires `ffmpeg`; override the UI with `AGENT_CHAT_WEB_URL`). It fails instead
of publishing if the model identity, complete memory acknowledgement/recall, or
browser-error checks fail.

This package is its own uv workspace (not part of the repo root workspace);
run everything from this directory. A root-level pytest run skips this tree
by design (see the collection guard in `conftest.py`).

## Notes and honest limits

- The SQLite stores are for local dev/tests; production uses Postgres
  (`database_url` switches). The SQLite vector store scans in Python — fine at
  template scale, not for large corpora.
- `send_message` is the template's one consequential, approval-gated tool —
  replace it with your own side-effecting tools behind the same
  `ApprovalGate` protocol.
- HNSW indexing is created by `PgVectorStore.init()`; embedding quality with
  the hashing embedder is lexical, not semantic — switch to MiniLM for real
  retrieval.
- File notebooks use atomic replacement but not cross-process compare-and-swap;
  move to a transactional `NotebookStore` for concurrent writers. Recalled notes
  are untrusted user content, not a secret store or an authorization boundary.
- Anonymous sessions prevent accidental cross-tab state sharing; they are not
  authentication or secure deletion. Closing a tab starts a new namespace, while
  old server-side files/rows remain until the adopter's retention job removes them.
