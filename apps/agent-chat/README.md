# agent-chat

A production-grade, **lift-out-able** chatbot-agent template: one generic,
modular agent you copy out of this repo and adapt. Built on pydantic-ai v2 +
FastAPI + Postgres/pgvector, with deterministic tests (a scripted fake model —
no network, no API keys) and a real eval suite behind the same graders.

```
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
├── memory/           # Conversation stores + per-user notebook + history processors
├── evals/            # 13-case pydantic-evals suite + markdown reports
└── api/              # FastAPI: SSE chat, approvals, conversations CRUD, ingest, health
infra/                # docker-compose (Postgres 16 + pgvector), multi-stage Dockerfile
tests/                # unit + API suites, all against the fake model and SQLite
```

## Quickstart (docker)

```bash
cd infra
docker compose up --build                        # api on :8000, Postgres 16 + pgvector behind it
docker compose --profile tools run --rm ingest   # one-shot: ingest ./docs into the vector store
```

The compose stack uses the dependency-free hashing embedder so it runs without
downloading torch. For semantic embeddings, install the extra and switch the
env (see "Embeddings" below).

## Quickstart (local, no docker)

```bash
uv sync                          # own venv inside this directory; Python 3.12.9
export AGENT_CHAT_EMBEDDER=hashing          # or: uv sync --extra embeddings
uv run uvicorn --factory agent_chat.api.app:create_app --port 8000
```

Defaults target a local Ollama (`qwen3:8b`) with a SQLite file for storage —
nothing else to install. Hosted OpenAI-compatible providers work too:

```bash
export AGENT_CHAT_PROVIDER=hosted \
       AGENT_CHAT_HOSTED_BASE_URL=https://api.example.com/v1 \
       AGENT_CHAT_HOSTED_API_KEY=... \
       AGENT_CHAT_HOSTED_MODEL=...
```

## The API

- `POST /chat` — body `{"message": "...", "conversation_id": "...", "user_id": "local"}`;
  `conversation_id` and `user_id` are optional. The user id scopes persistent
  notes (an authenticated deployment should derive it from the principal, not
  trust a browser-supplied id). The route streams SSE events: `text_delta`,
  `tool_call_start`/`tool_call_end`,
  `approval_request`/`approval_response` (the consequential `send_message`
  tool waits for a human; timeout = deny), `done` (typed `Answer` + usage +
  conversation id), `error`. Answer with `POST /approvals/{id}` and body
  `{"approved": true}`.
- `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}`
- `POST /ingest` — body `{"paths": ["docs/"]}`; chunk + embed + index
- `GET /health`, `GET /ready` — liveness and readiness (store probes)
- Every response carries `X-Request-ID`; errors are a structured envelope:
  `{"error": {"code", "message", "request_id"}}`. Set `AGENT_CHAT_API_KEY`
  to require an `X-API-Key` header on chat/mutations.

## Persistent memory without prompt bloat

`memory/notebook.py` follows pydantic-ai Harness Memory's on-demand pattern.
There is one `<user_id>.json` notebook per user under
`AGENT_CHAT_MEMORY_DATA_DIR` (default `./agent_chat_memory`). Each versioned file
contains notes with a stable id, fact, and UTC timestamp; atomic replacement
makes completed writes visible to a later process. `remember` stores an explicit
user fact. `recall` ranks literal term matches and returns at most five notes by
default (hard bound ten). The user id comes from `ChatDeps`, never model args.

There is deliberately **no automatic notebook injection**: instructions describe
when to call the tools, and only the selected recall results enter the model's
context. A thousand stored notes therefore do not become a thousand prompt
notes. Recall is lexical, not semantic; implement the two-method `NotebookStore`
protocol to swap in indexed retrieval without changing the agent tools.

Conversation history is bounded separately in `memory/history.py`. The default
`ProcessHistory` keeps the last `AGENT_CHAT_HISTORY_MAX_TURNS=10` user turns,
including tool legs, with no model call. Set
`AGENT_CHAT_HISTORY_SUMMARIZE_ENABLED=true` to summarize only overflow turns
with the configured model; the recent window remains verbatim. The template's
whole-Conversation store persists this bounded result. Keep durable user facts
in the notebook, and add an append-only store if you need a full audit transcript.
See `specs/decisions/0005-memory-harness.md` for the policy and concurrency limits.

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
4. **Budgets** — `config.py` usage limits (per-run requests/tokens),
   `approval_timeout_s`, `model_retries`.
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

The 13 cases grade answer correctness, exact tool choice, citation behavior,
refusal probes, approval flow, and a fact written in one run then recalled in a
fresh run — with deterministic graders (no LLM in the judge). CI runs them
against the fake; `--model real` grades your actual deployment with the same
graders.

## Tests

`tests/` covers tools, skills, RAG (SQLite-backed), notebook persistence and
recall bounds, history trim/summarize, the agent, the API, and an eval-suite
smoke run — all deterministic.

```bash
uv run pytest -q                                  # 95 tests, fully offline
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests                             # strict
```

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
