# AI Document Intelligence Workbench

**AI summarizes and organizes page by page; deterministic code verifies every
citation against the parsed PDF.**

A standalone, production-shaped workbench for born-digital PDFs. Each page gets
one bounded Pydantic AI call producing a cited summary, typed entities, and
topics, with per-page progress and per-page failure isolation. A separate
read-only agent answers questions about a selected page with exact source
citations. There is no review or approval workflow: the analysis you download
is the analysis the model produced, with deterministic validation issues made
visible.

## Capabilities

- **Page-level analysis:** every page is parsed, summarized, and mined for
  entities and topics independently, with progress persisted after each page.
- **Entity extraction:** literal mentions, normalized names, types, and source
  citations per page.
- **Cited page chat:** ask about one selected page; the answer carries exact,
  page-scoped citations. Conversations are ephemeral — nothing is persisted.
- **Downloads:** canonical JSON and readable Markdown exports for the full
  document or a single page, including progress and unresolved issues.
- **Operations:** tenant-scoped storage, a leased Postgres worker with bounded
  page concurrency, bounded retries, and append-only operational audit events.

The model never supplies trusted page numbers or bounding boxes. PyMuPDF owns
the coordinates. Deterministic code resolves every quote against the page's
text spans, extracted table lines, and image placeholders after a unicode
compatibility fold (ligatures, curly quotes, dashes). Quotes that occur on
several passages resolve to the first whole-passage match and surface a
warning; quotes that match nothing stay visible as errors on that page.
Document text is untrusted input; analysis and chat agents have no tools or
write capabilities.

## Quick start

Requires Python 3.12 and `uv`. Offline fixtures need no database, network,
model, or API key.

```bash
cd apps/document-intelligence
uv sync --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests scripts migrations
uv run uvicorn --factory document_intelligence.api.app:create_app --port 8001
```

Open `http://localhost:8001/docs`. Development identity requires
`X-Dev-Tenant: demo` and `X-Dev-Actor: analyst`; it is rejected in production.
The bare API command does not start a worker. Use the Compose stack for the
full upload-to-analysis flow.

The default analyzer and chat implementations are deterministic development
fixtures, **not AI-quality baselines**. Configure `page-analysis-v1` with a
real provider for document understanding.

## Postgres, API, worker, and UI

```bash
docker compose -f infra/docker-compose.yml up --build
# API: http://localhost:8001; migration completes before API and worker.
uv run python scripts/smoke_compose.py

cd web
npm ci
npm run dev
```

The Vite UI defaults to `http://localhost:4323` and proxies API requests to port
8001. The compose API is bound to `127.0.0.1`; identity mode, environment,
gateway shared secret, and the database password are compose env overrides.
Production must use Postgres and
`DOCUMENT_INTELLIGENCE_IDENTITY_MODE=gateway`; unsigned tenant headers are not
authentication. See `specs/operations.md` for identity, web serving, and
rate limiting.

## AI provider

Set the following through your process manager or secret manager:

```text
DOCUMENT_INTELLIGENCE_ANALYZER_BACKEND=model
DOCUMENT_INTELLIGENCE_PROVIDER=kimi
DOCUMENT_INTELLIGENCE_MODEL_NAME=kimi-k2.5
DOCUMENT_INTELLIGENCE_MODEL_BASE_URL=https://api.moonshot.ai/v1
DOCUMENT_INTELLIGENCE_MODEL_API_KEY=<secret>
```

The adapter works with Kimi and compatible OpenAI-style structured-output
providers. The analyzer makes one bounded call per page; page chat is a
separate bounded call. Request/token limits and bounded retries are configured
through the application settings; provider-side budgets remain necessary.

## HTTP surface

- `POST /documents` — upload a born-digital PDF; tenant+SHA256 duplicates return
  the existing document without another job.
- `GET /documents`, `/documents/queue`, `/documents/{id}` — list, queue, detail.
  Document status is `uploaded`, `processing`, `completed`, or `failed`.
- `GET /documents/{id}/content` — original tenant-authorized PDF.
- `GET /documents/{id}/analysis` — `{document, analysis, progress, analyzer,
  created_at, updated_at}`; `analysis` is `page-analysis-v1` or null while
  unprocessed. Poll `progress` for per-page completion.
- `POST /documents/{id}/reanalyze` — queue a fresh run; resets and overwrites
  analysis progress (202, idempotent per stage; 409 while the document is
  still `processing`).
- `POST /documents/{id}/pages/{page}/chat` — cited answer about one page;
  body `{messages: [...]}` with 1–20 messages; the last message must have
  role `user` and is the one answered.
- `GET /documents/{id}/analysis/export?format=json|md` — full-document report.
- `GET /documents/{id}/pages/{page}/export?format=json|md` — single-page report.
- `GET /health`, `/ready` — liveness and adapter readiness.

Removed with the review workflow: classification, corpus themes, revisions,
corrections, decisions, audit exports, whole-document `ask`, and CSV export.
There is intentionally no review state to query.

Errors use `{"error":{"code","message","request_id"}}`. Unknown and
cross-tenant documents return 404; unknown pages return `page_not_found` 404;
reanalysis of a processing document returns `document_busy` 409; validation
failures return 422. All API payloads reject unknown fields.

## Pages, tables, and images

The parser emits one `ParsedPage` per PDF page: born-digital text spans with
PDF coordinates, tables detected through `page.find_tables()` when the
installed PyMuPDF provides it, and image blocks counted with explicit
placeholders appended to the model-facing text (for example
`[image 1 on page 3: no extractable text; image content is not OCRed]`).
Extracted table text is appended so models can analyze it.

**No raster OCR is performed or claimed.** Scanned pages yield placeholders and
counts, not transcriptions. Model-facing page text is clipped per
`DOCUMENT_INTELLIGENCE_PAGE_TEXT_MAX_CHARS` (default 24000) to bound prompts;
parser spans stay complete so evidence resolution still covers the full page.
The worker analyzes pages with bounded concurrency
(`DOCUMENT_INTELLIGENCE_PAGE_CONCURRENCY`, default 3, max 5) and persists
progress after every page, so a pathological or failing page never blocks the
rest of the document — the failure stays on that page and the document still
completes. The document itself is `failed` only when the whole job fails
(unreadable PDF, terminal retries); inspect `progress` and per-page `error`.

## Fixtures and evaluation

`fixtures/` contains seven committed synthetic born-digital PDFs: a multipage
research report, fictional CVs, a quarterly report, a services contract, field
notes, a prompt-injection case, and an inventory page with a ruling-detected
table and an embedded image. Reserved example identities keep personal data
out of the repository. Regenerate backend and browser copies together and run
the evaluation with:

```bash
uv run python scripts/generate_fixtures.py
uv run document-intelligence-eval --output reports/offline-metrics.json
# Explicit provider opt-in after reviewing cost:
uv run document-intelligence-eval --live --output reports/live-metrics.json
```

The versioned page-level harness evaluates, per reference page: summary
key-point coverage and citation support, entity precision/recall/F1 and type
accuracy, multi-label topic metrics, page-chat correctness and citation
support, evidence resolvability, expected table/image counts, plus
`page_failure_rate` (failed pages over analyzed pages) and
`analysis_miss_rate` (reference pages with any miss over reference pages).
Latency, usage, and configurable cost are reported with per-page misses and run
errors. The review-era classification and correction-rate metrics were removed.
Offline output verifies the application path only; it is not presented as model
accuracy. Reports retain per-page misses and run errors rather than hiding
failed cases.

`reports/offline-metrics.json` reflects the current page-analysis-v1 path.
`reports/live-metrics.json` is a current page-analysis-v1 run, measured on
2026-11-08 with `kimi:kimi-for-coding` on the committed synthetic corpus
(revision 2026-11-08.1, 7 cases, zero provider errors, page failure rate 0.0).
Headline measured numbers: chat answer accuracy 1.00 with reference citations
1.00; evidence resolvability 1.00; unsupported citation rate 0.00; summary
key-point coverage 0.82 with citation support 0.82; entity F1 0.68 (recall
0.96, precision 0.52, type accuracy 0.96); topic F1 0.50; median latency
38.5s per case (31.9s analysis, 6.6s chat). Remaining per-page misses are
entity/topic over-extraction against compact references plus run-to-run model
variance; the any-miss rule puts the page-level analysis miss rate at 1.00.
Resolution tolerates repeated passages (first whole-passage match plus a
warning) and unicode variants, so citation errors are gone from these cases.
Regenerate with a configured provider after model, prompt, schema, parser, or
reference changes.

## Source map

- `src/document_intelligence/domain/` — strict `page-analysis-v1` models.
- `src/document_intelligence/analysis/` — Pydantic AI page analyzer, page chat,
  evidence resolution/validation, workflow service, exports.
- `src/document_intelligence/documents/` — per-page PDF parsing and blobs.
- `src/document_intelligence/jobs/` — leased in-memory/Postgres queues.
- `src/document_intelligence/store/` — repositories, analysis table models.
- `src/document_intelligence/api/` — tenant-scoped FastAPI application.
- `web/` — React PDF viewer and page-analysis workbench (separate owner).
- `specs/architecture.md` — trust boundaries and data model.
- `specs/operations.md` — setup, deployment, recovery, and evaluation.
