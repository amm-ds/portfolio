import type { DiagramSpec } from "./types";

// Facts: apps/document-intelligence/{specs/architecture.md,README.md,reports/live-metrics.json}.
export const DOCUMENT_INTELLIGENCE_ARCHITECTURE_SPEC = {
  id: "app-document-intelligence-architecture",
  title: "Upload → cited pages: the document intelligence pipeline",
  direction: "LR",
  canvasHeight: 560,
  nodes: [
    {
      id: "workbench",
      label: "React workbench",
      kind: "source",
      facts: [
        "The static TypeScript client renders the PDF and overlays only backend-resolved coordinates; it never asserts evidence or tenant identity for the server.",
        "A per-page progress rail shows which pages are done, running, or failed while the worker continues.",
      ],
    },
    {
      id: "api",
      label: "FastAPI surface",
      kind: "api",
      facts: [
        "POST /documents uploads a born-digital PDF; tenant+SHA256 duplicates return the existing document without another job.",
        "Unknown and cross-tenant documents return 404; errors use the {error: {code, message, request_id}} envelope and payloads reject unknown fields.",
      ],
    },
    {
      id: "queue",
      label: "leased job queue",
      kind: "data",
      facts: [
        "Jobs have expiring leases, owner-checked heartbeats, bounded attempts, and exponential retry backoff; acquisition uses FOR UPDATE SKIP LOCKED.",
        "A partial unique index prevents duplicate active tenant+document+stage jobs; reanalysis of a processing document returns 409.",
      ],
    },
    {
      id: "worker",
      label: "worker · bounded page concurrency",
      kind: "agent",
      facts: [
        "The worker parses once per run and analyzes pages under a semaphore (default 3, max 5 concurrent pages).",
        "A page result is applied only while its job id still owns the row, so a superseded run cannot clobber a newer one.",
      ],
    },
    {
      id: "parser",
      label: "PyMuPDF per-page parse",
      kind: "tool",
      facts: [
        "One ParsedPage per PDF page: text spans with page-relative coordinates, ruling-detected tables via page.find_tables(), and image blocks as explicit placeholders.",
        "No raster OCR is performed or claimed; model-facing page text is clipped (default 24,000 chars) while spans stay complete for evidence resolution.",
      ],
    },
    {
      id: "analyzer",
      label: "tool-free Pydantic AI · one call per page",
      kind: "model",
      facts: [
        "One structured call per page receives only delimited, untrusted page text, table text, and image placeholders; the agent has no tools or write path.",
        "An output validator requires at least one key point and one topic on pages with content.",
      ],
    },
    {
      id: "evidence",
      label: "deterministic evidence resolution",
      kind: "gate",
      facts: [
        "Model-supplied coordinates are discarded; quotes match text spans, extracted table lines, and image placeholders after a unicode compatibility fold (ligatures, curly quotes, dashes).",
        "A quote on several passages resolves to the first whole-passage match with a warning; an unmatched quote stays a visible error; entity text must occur literally in its quote.",
        "Measured evidence resolvability is 1.00 with an unsupported citation rate of 0.00 (reports/live-metrics.json, 2026-11-08).",
      ],
    },
    {
      id: "analysis",
      label: "per-page analysis · summary + entities + topics",
      kind: "data",
      facts: [
        "page-analysis-v1 carries per-page status, error, and issues, plus a cited summary, typed entities, and topics from the single call.",
        "Measured with kimi:kimi-for-coding: entity F1 0.68 (recall 0.96, precision 0.52) and topic F1 0.50; per-page misses stay in the report.",
      ],
    },
    {
      id: "progress",
      label: "progress persisted per page",
      kind: "data",
      facts: [
        "AnalysisProgress reports page_count, processed_pages, and failed_pages; a single-row update after every page avoids N+1 scans.",
        "Per-page failures stay on their page; the document completes when every page finishes and fails only on a terminal whole-job error.",
      ],
    },
    {
      id: "chat",
      label: "cited page chat",
      kind: "agent",
      facts: [
        "A separate read-only agent answers about one selected page over 1-20 bounded messages; conversations are ephemeral and nothing is persisted.",
        "Every chat citation is re-resolved against the page; an absent or ambiguous citation rejects the whole answer.",
        "Measured chat answer accuracy is 1.00 with reference citations 1.00 (reports/live-metrics.json, 2026-11-08).",
      ],
    },
  ],
  edges: [
    { id: "workbench-api", source: "workbench", target: "api", kind: "task", label: "POST /documents" },
    { id: "api-queue", source: "api", target: "queue", kind: "task", label: "analyze / reanalyze" },
    { id: "queue-worker", source: "queue", target: "worker", kind: "task", label: "lease + heartbeat" },
    { id: "worker-parser", source: "worker", target: "parser", kind: "task", label: "parse once per run" },
    { id: "parser-analyzer", source: "parser", target: "analyzer", kind: "task", label: "delimited untrusted page" },
    { id: "analyzer-evidence", source: "analyzer", target: "evidence", kind: "task", label: "typed output" },
    { id: "evidence-analysis", source: "evidence", target: "analysis", kind: "result", label: "resolved + validated" },
    { id: "analysis-progress", source: "analysis", target: "progress", kind: "result", label: "apply per page" },
    { id: "progress-workbench", source: "progress", target: "workbench", kind: "result", label: "poll progress" },
    { id: "workbench-chat", source: "workbench", target: "chat", kind: "task", label: "question + history" },
    { id: "parser-chat", source: "parser", target: "chat", kind: "task", label: "selected page text" },
    { id: "chat-workbench", source: "chat", target: "workbench", kind: "result", label: "cited answer" },
  ],
} as const satisfies DiagramSpec;
