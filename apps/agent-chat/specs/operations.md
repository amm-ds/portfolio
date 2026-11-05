# agent-chat — Operations

Runbook for bringing the stack up, keeping it healthy, and getting out of
trouble. Everything below runs from `apps/agent-chat/` (docker) or
`apps/agent-chat/infra/` (compose commands).

## Bring-up (docker)

Prerequisite: a local Ollama serving the configured model
(`qwen3:8b` by default — `ollama pull qwen3:8b` if it is missing).

```bash
cd infra
docker compose up --build                 # api on http://localhost:8000
docker compose --profile tools run --rm ingest   # one-shot: index ./docs
```

The compose stack sets three overrides (see `infra/docker-compose.yml`):

- `AGENT_CHAT_DATABASE_URL=postgresql+asyncpg://agent_chat:agent_chat@db:5432/agent_chat`
- `AGENT_CHAT_EMBEDDER=hashing` (the image excludes the `[embeddings]` extra
  because torch is ~GBs — see "Embeddings" below)
- `AGENT_CHAT_OLLAMA_BASE_URL=http://host.docker.internal:11434`

The API container waits for the `db` healthcheck (`pg_isready`, 5 s interval,
12 retries) before starting. `PgVectorStore.init()` creates the extension,
table, and HNSW index on first startup — there is no migration step.

## Bring-up (local, no docker)

```bash
uv sync                                  # own venv; Python 3.12.9
export AGENT_CHAT_EMBEDDER=hashing       # or: uv sync --extra embeddings
uv run uvicorn --factory agent_chat.api.app:create_app --port 8000
```

Defaults target a local Ollama and a SQLite file (`agent_chat.db`) — nothing
else to install. Hosted providers instead of Ollama:

```bash
export AGENT_CHAT_PROVIDER=hosted \
       AGENT_CHAT_HOSTED_BASE_URL=https://api.example.com/v1 \
       AGENT_CHAT_HOSTED_API_KEY=... \
       AGENT_CHAT_HOSTED_MODEL=...
```

## Ingest

Three equivalent ways to load the knowledge base (markdown/txt only):

```bash
# one-shot compose service (mounts ../docs read-only)
docker compose --profile tools run --rm ingest

# CLI inside or outside docker
uv run agent-chat-ingest ./docs

# HTTP (requires X-API-Key when AGENT_CHAT_API_KEY is set)
curl -X POST localhost:8000/ingest -H 'content-type: application/json' \
     -d '{"paths": ["docs/"]}'
```

Chunking is paragraph-first, ≤500 chars with 50-char overlap; the response
counts files and chunks. Ingesting the same file twice duplicates chunks
(versioning is out of scope) — clear the store first:

```bash
docker compose exec db psql -U agent_chat agent_chat -c 'TRUNCATE TABLE rag_chunks'
# or for the local SQLite file: uv run python -c "import sqlite3, pathlib; \
#   p = pathlib.Path('agent_chat.db'); c = sqlite3.connect(p); \
#   c.execute('DELETE FROM rag_chunks'); c.commit()"
```

A re-ingest is also required after changing the embedder (the vector space
changes), and after switching from SQLite to Postgres (different store).

## Health checks

- `GET /health` — liveness; answers without touching anything.
- `GET /ready` — readiness; pings the conversation store and the vector
  store, 503 with the failing probe (`database not reachable` / `vector store
  not reachable`) until both answer.
- Compose `db` healthcheck — `pg_isready -U agent_chat -d agent_chat`.
- Every response (including SSE) carries `X-Request-ID`; errors are the
  structured envelope `{"error": {"code", "message", "request_id"}}`.

```bash
curl -fsS localhost:8000/health && curl -fsS localhost:8000/ready
```

## Logs

```bash
docker compose logs -f api     # uvicorn access + app logs; unhandled errors
                               # are logged with the URL path before the 500
docker compose logs -f db      # postgres; look here for auth and extension errors
```

## Backups

The template ships no backup automation — these are the manual paths, both
standard Postgres:

```bash
# backup (run from infra/)
docker compose exec db pg_dump -U agent_chat agent_chat \
  | gzip > "agent_chat-$(date +%F).sql.gz"

# restore into a fresh volume
gunzip -c agent_chat-2026-11-05.sql.gz \
  | docker compose exec -T db psql -U agent_chat agent_chat
```

For the local SQLite dev file, copy `agent_chat.db` while the API is stopped
(SQLite tolerates hot copies via `.backup`, but a stopped process is the
simple honest path at this scale). Conversations are self-contained JSON rows;
the vector store can always be rebuilt with a re-ingest.

## Environment reference

Every knob, prefix `AGENT_CHAT_` (pydantic-settings; `.env` in the working
directory is read too).

| variable | default | meaning |
|---|---|---|
| `PROVIDER` | `ollama` | `ollama` or `hosted` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | local Ollama base (compose overrides with `host.docker.internal:11434`) |
| `OLLAMA_MODEL` | `qwen3:8b` | primary local model |
| `OLLAMA_FALLBACK_MODEL` | `""` | secondary local model; set to enable a `FallbackModel` chain |
| `HOSTED_BASE_URL` | `""` | OpenAI-compatible base URL |
| `HOSTED_API_KEY` | `""` | key for the hosted provider |
| `HOSTED_MODEL` | `""` | primary hosted model |
| `HOSTED_FALLBACK_MODEL` | `""` | secondary hosted model |
| `MODEL_RETRIES` | `2` | pydantic-ai retries on output-validation failure |
| `USAGE_REQUEST_LIMIT` | `30` | per-run request budget (0 = unlimited) |
| `USAGE_INPUT_TOKENS_LIMIT` | `100000` | per-run input-token budget (0 = unlimited) |
| `USAGE_OUTPUT_TOKENS_LIMIT` | `20000` | per-run output-token budget (0 = unlimited) |
| `DATABASE_URL` | `sqlite:///./agent_chat.db` | `postgres*` selects Postgres/pgvector, otherwise SQLite |
| `EMBEDDER` | `minilm` | `minilm` (semantic, needs the `embeddings` extra) or `hashing` (lexical, zero deps) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | local sentence-transformers model name |
| `API_KEY` | `""` | set to require `X-API-Key` on chat/mutations (compared with `hmac.compare_digest`) |
| `APPROVAL_TIMEOUT_S` | `120` | seconds to await a human decision; timeout = deny |
| `FETCH_URL_ENABLED` | `false` | attach the opt-in network tool (`fetch_url`) |
| `SKILLS_DIR` | package `skills/` | where skill folders are loaded from |

## Common failures

| symptom | cause | fix |
|---|---|---|
| `/ready` 503, "database not reachable" | db container still starting or down | `docker compose ps`; wait for the healthcheck, `docker compose up -d db` |
| `/chat` streams an `error` event, code `APIConnectionError` (or similar) | Ollama not running, model not pulled, or unreachable from the container | `ollama list`; on Linux add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `api` service — the shortcut hostname is not resolvable on stock Linux Docker |
| 401 on chat/mutations | `AGENT_CHAT_API_KEY` set, `X-API-Key` missing/mismatched | send the header, or unset the variable |
| 404 "unknown conversation '…'" | stale `conversation_id` from an old store | list via `GET /conversations`, start a new one |
| 404 "no pending approval '…'" | id settled already or typo'd | decisions are one-shot; settle each id once |
| `send_message` reports denial with nobody clicking deny | the 120 s approval timeout fired | raise `AGENT_CHAT_APPROVAL_TIMEOUT_S`, or answer faster — timeout = deny by design |
| `RuntimeError` about the embeddings extra at startup | `EMBEDDER=minilm` without torch | `uv sync --extra embeddings`, or `AGENT_CHAT_EMBEDDER=hashing` |
| Retrieval returns nothing relevant | hashing embedder is lexical, or nothing ingested | expect lexical-only ranking with `hashing`; switch to `minilm` and re-ingest |
| Duplicated answers after repeated ingest | chunks were added twice | `TRUNCATE TABLE rag_chunks`, re-ingest |
| 422 with `validation_error` envelope | malformed body (message >8000 chars, empty paths, …) | check the envelope message; bounds are in the route models |

## Tests and evals as ops checks

```bash
uv run pytest -q                                       # 95 tests, fully offline
uv run python -m agent_chat.evals.runner               # 13 cases vs the fake model
uv run python -m agent_chat.evals.runner --model real  # same graders vs your deployment
```

`--model real` is the post-change smoke check: same cases, same deterministic
graders, but the model you actually run — read `reports/evals.md` after it.
