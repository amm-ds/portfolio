# Architecture

## System boundary

**AI proposes cited page analysis; deterministic code owns evidence.**

```text
authenticated identity
        |
PDF upload -> tenant + SHA256 document -> leased analyze job
        |                                   |
        |                    parse once: per-page text spans, tables,
        |                    image placeholders, parser-owned bboxes
        |                                   |
        |              bounded page concurrency (semaphore, default 3)
        |                 one tool-free Pydantic AI call per page
        |                                   |
        |                 summary + entities + topics per page
        |                                   |
        |        deterministic quote-to-source resolution per page
        |                                   |
        |   document_analyses row: progress after every page,
        |   per-page failures stay on their page
        |                                   |
        +------------------ document completed when all pages finish
                                |
                 JSON / Markdown downloads (document or page)

selected page text + bounded history -> tool-free chat agent
        -> cited answer (read-only: no persistence, no workflow mutation)
```

The application is an independent uv workspace. The Compose deployment runs
Postgres, Alembic migration, FastAPI, and a separate worker. The React UI is a
static TypeScript client; it never asserts evidence coordinates or tenant
identity on behalf of the server.

There is no human review path. The previous whole-document analysis with
classifications, corpus themes, revisions, corrections, decisions, and audit
exports was removed; operational audit events (upload, analysis started/
completed, reanalysis requested) remain in the append-only `audit_events`
table but have no public route.

## Page-analysis contract

All models inherit a strict Pydantic base with unknown fields forbidden.
`PageAnalysisResult` has discriminator `page-analysis-v1` and contains one
`PageAnalysis` per parsed page:

- `page`, `status` (`completed` | `failed`), per-page `error`, `issues`.
- `PageSummary`: one page-scoped summary plus `CitedText` key points.
- `PageEntity[]`: literal source `text`, normalized `name`, `type`, one citation.
- `PageTopic[]`: label, rationale, and supporting citations.
- `text_chars`, `image_count`, `table_count` from the parser.

Entity types use a small shared taxonomy (`person`, `organization`, `email`,
`date`, `money`, `location`, `skill`, `job_title`, `equipment`, `document_id`,
`region`, `other`). The UI mirrors the list so unsupported labels cannot
appear. Topic labels remain open, concise natural language.

`AnalysisProgress` reports `page_count`, `processed_pages`, and `failed_pages`
for UI polling. `AnalysisResponse` embeds the document record, the nullable
analysis, progress, analyzer name, and analysis timestamps. `PageChatRequest`
carries 1–20 bounded messages and requires the last message to have role
`user`; that message is answered with at least one resolved citation.

The contract deliberately has no arbitrary model confidence field. Topic labels
and entity types are reviewable model outputs, while exact citations are
deterministic application facts.

## Parser boundaries

`documents/parser.py` emits one `ParsedPage` per PDF page using PyMuPDF text
spans with page-relative coordinates. Tables are detected with
`page.find_tables()` when available (the call is guarded because the table API
varies across PyMuPDF versions); extracted table text is appended to the
model-facing page text so models can reason about it. Image blocks are counted
and rendered as explicit placeholders so image-only pages are represented as
images, not as empty text. **No raster OCR is performed or claimed**; image
pixels never become text. Model-facing page text is clipped per
`page_text_max_chars` to avoid pathological pages; spans remain complete so
evidence resolution covers the full page.

## AI and evidence boundaries

The analyzer makes one structured Pydantic AI call per page. It receives only
delimited, untrusted page text, table text, and image placeholders; an output
validator requires at least one key point and one topic on pages with content.
The chat agent is a separate bounded structured call over one selected page
and a bounded message history, returning a cited answer. Neither agent has
tools, repository/blob dependencies, or an application write path, so embedded
instructions have no action to invoke. Bounded retries, request/token limits,
and provider configuration constrain external calls.

`analysis/evidence.py` discards incoming coordinates and resolves quotes
against the page's text spans, extracted table lines, and image placeholders
after a unicode compatibility fold (ligatures, curly quotes, dashes). The
page and bounding box come only from matching PyMuPDF-owned geometry. Quotes
that match several passages resolve to the first whole-passage match and
produce a warning issue; quotes that match nothing produce an error issue on
that page instead of trusted coordinates. Entity mentions must occur
literally in their cited quote. Every key point, entity, and topic is
checked. Validation also requires at least one key point and one topic on
pages with content.

The deterministic analyzer and chat are offline functional adapters. They make
the API, worker, UI, and tests reproducible without credentials; they are not
an AI-quality baseline and their output is never published as model accuracy.

## Persistence and tenant isolation

The repository protocol has in-memory and Postgres implementations sharing one
contract:

- unique tenant+SHA256 documents;
- one `document_analyses` row per document keyed by document id, holding
  tenant, analyzer, nullable analysis JSON, page_count/processed_pages/
  failed_pages, job id, and timestamps;
- single-row progress updates after every page (no N+1 scans);
- tenant predicates on every document-scoped read;
- append-only operational audit events in Postgres.

Reanalysis overwrites the analysis row and resets progress; a page result is
only applied when its job id still owns the row, so a superseded run cannot
clobber a newer one. Blobs live under `<tenant>/<sha256>.pdf`. Local storage
uses atomic writes; the S3-compatible adapter uses the normal AWS credential
chain.

The page-analysis rebuild replaces review-era tables through an explicit
one-way migration (0003) that preserves generic documents, jobs, and audit
events. It does not translate incompatible historical payloads. Operators must
back up app data before applying that migration.

## Queue and failure semantics

Uploads queue `analyze`; explicit new runs queue `reanalyze`. A reanalysis
request for a document whose status is still `processing` is rejected with a
409 conflict instead of queueing a second run. Jobs have expiring
leases, owner-checked heartbeats, bounded attempts, and exponential retry
backoff. Postgres acquisition uses `FOR UPDATE SKIP LOCKED`. A partial unique
index prevents duplicate active tenant+document+stage jobs, so duplicate
requests stay idempotent.

The worker parses once per run, analyzes pages with bounded concurrency, and
persists progress after every page. Individual page failures stay on that page;
the document is marked `completed` once every page finished, with
`failed_pages` reporting the residue. The document becomes `failed` only when
the whole job fails terminally (unreadable PDF, exhausted retries). A
terminally failed job preserves its error for inspection and reanalysis.
Exactly-once external model calls are not claimed; persistence stages are
idempotent.

## API identity

Development identity is available only outside production. Gateway mode accepts
tenant and actor only in a timestamped HMAC-SHA256-signed envelope with bounded
clock skew. A bare tenant header is not authentication. Health endpoints are
public; every document route, including page chat and exports, requires
identity. Unknown and cross-tenant documents both return 404, as do unknown
pages.

## Evaluation

One versioned page-level runner evaluates all capabilities against committed,
non-sensitive per-page references: summary key-point coverage and citation
support, entity precision/recall/F1 and type accuracy, multi-label topic
metrics, page-chat correctness and citation support, evidence resolvability,
expected table/image counts, `page_failure_rate`, and `analysis_miss_rate`
(defined as reference pages with any miss over reference pages; the review-era
correction rate no longer exists). Classification metrics were removed with the
classifier. Cross-cutting latency, usage, and configurable cost are included.

The report records model/provider, schema and prompt version, dataset revision,
timestamp, per-page misses, and provider failures. Small synthetic fixtures
verify behavior and regressions; they do not establish universal accuracy, OCR,
handwriting support, straight-through processing, or ROI.
