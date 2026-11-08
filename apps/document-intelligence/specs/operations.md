# Operations

## Local development

```bash
cd apps/document-intelligence
uv sync --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests scripts migrations
uv run uvicorn --factory document_intelligence.api.app:create_app --host 0.0.0.0 --port 8001
```

Defaults are in-memory persistence, local blobs, deterministic analysis/chat,
and development identity. They support tests and local UI only. Do not run
multiple API/worker processes against the in-memory adapters and do not
describe offline output as AI quality.

Use `uv run --env-file .env ...` or a process supervisor to load a copied
`.env.example`. Keep credentials and personal documents out of version control.

## Compose stack

```bash
docker compose -f infra/docker-compose.yml up --build db migrate
docker compose -f infra/docker-compose.yml up --build api worker
docker compose -f infra/docker-compose.yml ps
curl http://localhost:8001/health
curl http://localhost:8001/ready
uv run python scripts/smoke_compose.py
```

The API port is bound to `127.0.0.1:8001`; db/api/worker restart unless
stopped, and api/worker carry healthchecks. Zero env vars gives the localhost
defaults (development identity, `review` database password). Compose
overrides for a non-default deployment:

```bash
DOCUMENT_INTELLIGENCE_IDENTITY_MODE=gateway \
DOCUMENT_INTELLIGENCE_ENVIRONMENT=production \
DOCUMENT_INTELLIGENCE_GATEWAY_SHARED_SECRET=<secret-manager injection> \
DOCUMENT_INTELLIGENCE_POSTGRES_PASSWORD=<strong password> \
  docker compose -f infra/docker-compose.yml up -d --build
```

Required for any non-localhost exposure: gateway identity mode, the shared
secret, and a real database password. The app refuses to boot in production
with development identity or an empty gateway secret; do not republish the API
port on a host interface without the gateway topology described under
"Web serving and rate limiting" below.

The smoke proves upload, real worker analysis with per-page progress, page
mode data (summary/key points, entities, topics, issues), cited page chat,
full-document and single-page JSON/Markdown downloads, duplicate suppression,
and cross-tenant denial. `migrate` finishes `alembic upgrade head` before API
or worker starts. Postgres and blobs use named volumes.

The page-analysis rebuild contains a one-way replacement migration (0003) for
app-owned tables: review-era raw analyses, revisions, and decisions are
dropped, and `document_analyses` is created keyed by document id while generic
documents, jobs, and audit events are preserved. Back up Postgres and blobs
before upgrading an existing installation; there is no incompatible-payload
backfill, and review-era statuses are reset to `uploaded`. Do not run a blind
downgrade against append-only production records.

Manual migration commands:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic upgrade head --sql  # inspect SQL without a live database
```

## Identity

Local development:

```text
DOCUMENT_INTELLIGENCE_ENVIRONMENT=development
DOCUMENT_INTELLIGENCE_IDENTITY_MODE=development
X-Dev-Tenant: <tenant>
X-Dev-Actor: <actor>
```

Production:

```text
DOCUMENT_INTELLIGENCE_ENVIRONMENT=production
DOCUMENT_INTELLIGENCE_IDENTITY_MODE=gateway
DOCUMENT_INTELLIGENCE_GATEWAY_SHARED_SECRET=<secret-manager injection>
```

The trusted gateway authenticates the user and sends `X-Gateway-Tenant`,
`X-Gateway-Actor`, `X-Gateway-Timestamp` (Unix seconds), and
`X-Gateway-Signature`. The lowercase hex HMAC-SHA256 message is exactly:

```text
v1\n<timestamp>\n<tenant>\n<actor>
```

Use TLS, strip client-supplied gateway headers at the edge, rotate the secret,
and never log it. Requests outside the configured timestamp skew
(`DOCUMENT_INTELLIGENCE_GATEWAY_MAX_SKEW_SECONDS`, default 300) fail.
Production with development identity or an empty gateway secret fails closed.

## Web serving and rate limiting

Production serves the React SPA build from the same origin as the API behind
the trusted gateway; the API deliberately has no CORS middleware, so a
split-origin deployment is not supported. Rate limiting is the gateway's job:
the app ships no limiter (documented gap). Terminate TLS, strip client-supplied
gateway headers, and enforce per-client limits at the gateway before traffic
reaches the API.

## Model configuration

```text
DOCUMENT_INTELLIGENCE_ANALYZER_BACKEND=model
DOCUMENT_INTELLIGENCE_PROVIDER=kimi
DOCUMENT_INTELLIGENCE_MODEL_NAME=kimi-k2.5
DOCUMENT_INTELLIGENCE_MODEL_BASE_URL=https://api.moonshot.ai/v1
DOCUMENT_INTELLIGENCE_MODEL_API_KEY=<secret-manager injection>
```

The same adapter supports compatible OpenAI-style structured-output providers.
Analysis makes one bounded model call per page; page chat is a separate
on-demand bounded call. Both are tool-free. Configure bounded retries and
request/token limits in application settings, plus provider-side budgets,
timeouts, and alerts. Persistence idempotency does not make external model
calls free or exactly once.

## Page pipeline limits

```text
DOCUMENT_INTELLIGENCE_PAGE_CONCURRENCY=3        # 1..5, per worker run
DOCUMENT_INTELLIGENCE_PAGE_TEXT_MAX_CHARS=24000 # model-facing text per page
DOCUMENT_INTELLIGENCE_MAX_UPLOAD_BYTES=10000000
```

Progress is stored on the single `document_analyses` row and updated after
every page, so UI polling reads one row. Page text clipping bounds pathological
pages; parser spans stay complete so citations still resolve across the full
page. Tables are detected with `page.find_tables()` when the installed PyMuPDF
provides it; extracted table text is appended to the page text. Images are
counted and represented by placeholders — **no raster OCR**: scanned pages are
reported as images, not transcribed.

## Blob storage

Local blobs are the default. For S3-compatible storage configure:

```text
DOCUMENT_INTELLIGENCE_BLOB_BACKEND=s3
DOCUMENT_INTELLIGENCE_S3_BUCKET=<bucket>
DOCUMENT_INTELLIGENCE_S3_PREFIX=documents
DOCUMENT_INTELLIGENCE_S3_ENDPOINT_URL=<optional>
DOCUMENT_INTELLIGENCE_S3_REGION=<optional>
```

Use the AWS provider chain for credentials. Apply encryption, private ACLs,
lifecycle rules, backup/restore tests, and tenant access controls appropriate to
document sensitivity.

## Worker and recovery

Production-shaped defaults:

- `DOCUMENT_INTELLIGENCE_LEASE_SECONDS=60`
- `DOCUMENT_INTELLIGENCE_HEARTBEAT_SECONDS=20`
- `DOCUMENT_INTELLIGENCE_MAX_JOB_ATTEMPTS=3`
- `DOCUMENT_INTELLIGENCE_WORKER_POLL_SECONDS=1`

Keep heartbeat comfortably below lease expiry. Retry delay is exponential.
Scale workers only with Postgres. SIGTERM shuts the worker down gracefully: it
finishes the current job, then closes the repository and queue connections.
Inspect `last_error` and the analysis
`progress`/`failed_pages` after terminal failure, then request
`/documents/{id}/reanalyze`; reanalysis resets and overwrites analysis state
for a fresh run (it returns 409 while a run for that document is still in
flight). Per-page failures need no action: they stay visible on the
page with their error, and the document still completes.

Back up the database and blobs together. A crash between independent blob,
document, and queue operations can require orphan cleanup or a new analysis
request. Progress writes and document transitions are single-row operations.

## Downloads and retention

`GET /documents/{id}/analysis/export?format=json|md` produces a full-document
report; `GET /documents/{id}/pages/{page}/export?format=json|md` produces a
single-page report. JSON is canonical sorted pretty JSON; Markdown includes
document metadata, progress, per-page summary/key points/entities/topics,
evidence quotes with resolved markers, and unresolved validation issues. Both
use the same tenant authorization as the source document. Page chat is
ephemeral and never persisted.

Define retention and legal-hold policy with the adopter. Append-only database
triggers intentionally prevent ORM updates/deletes on audit events; retention
requires an explicit migration and policy-driven runbook.

## Evaluation

```bash
uv run python scripts/generate_fixtures.py
uv run document-intelligence-eval --output reports/offline-metrics.json
# Only with a configured provider and intended live calls:
uv run document-intelligence-eval --live --output reports/live-metrics.json
```

Use `--input-cost-per-million` and `--output-cost-per-million` with current
provider prices before treating cost output as a budget. Inspect per-page
misses and `run_errors`; a completed report can still contain failed model
cases. Re-run after model, prompt, schema, parser, or reference changes. The
report's `page_failure_rate` and `analysis_miss_rate` replaced the review-era
correction rate; classification metrics no longer exist.

The committed `reports/live-metrics.json` records the last measured live run:
2026-11-08, `kimi:kimi-for-coding`, corpus revision 2026-11-08.1, 7 cases,
0 provider errors, page failure rate 0.0. Headline numbers: chat answer
accuracy 1.00, chat reference citation rate 1.00, evidence resolvability 1.00,
summary coverage 0.82, entity F1 0.68, topic F1 0.50, unsupported citation
rate 0.00, median case latency 38.5s. Remaining misses are over-extraction
and run-to-run model variance, not citation failures.

Committed fixtures are synthetic and born-digital. Before a real rollout, add a
representative approved corpus, define acceptance thresholds, test prompt
injection and tenant isolation, and perform a privacy/security review. The
prepared suite does not prove OCR, handwriting, universal accuracy, unattended
automation, or ROI.
