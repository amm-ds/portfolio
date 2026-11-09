import { AppArticleSection, AppScreenshot } from "../components/AppArticle";
import { Card } from "../components/Card";
import { LazyFlowDiagram } from "../components/diagrams/LazyFlowDiagram";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { renderMarkdown } from "../lib/markdown";
import { usePageMeta } from "../seo";

const REPO = "https://github.com/amm-ds/portfolio/tree/main/apps/document-intelligence";

const CONTRACT_SNIPPET = `\`\`\`python
class PageAnalysis(StrictModel):
    summary: Summary
    entities: list[Entity]
    topics: list[Topic]

# One coherent model call per page; every factual element carries source evidence.
# Chat is a separate, page-scoped read-only conversation contract.
\`\`\``;

const AGENT_SNIPPET = `\`\`\`python
result = await self.agent.run(
    "<untrusted_document_page>\\n" + page.text + "\\n</untrusted_document_page>",
    usage_limits=self.usage_limits,
    timeout=self.timeout_seconds,
)
return result.output

# No tools, repository, blob store, queue, or mutation capability.
\`\`\``;

const EVIDENCE_SNIPPET = `\`\`\`python
resolved = resolve_quote(quote, page)  # unicode-folded match over spans + table lines + image placeholders
if not resolved.resolved:
    issues.append(ValidationIssue(
        code="unresolved_evidence",  # severity "error": the quote matched nothing
        path=path,
        message="Quote must resolve to one passage on this page",
    ))
elif _resolve(quote, page)[1]:
    issues.append(ValidationIssue(
        code="ambiguous_evidence",  # severity "warning": first whole-passage match wins
        path=path,
        message="Quote matches multiple passages; coordinates point to the first match",
    ))

# Incoming model coordinates are discarded; PyMuPDF-owned geometry wins.
\`\`\``;

const EVAL_SNIPPET = `\`\`\`bash
cd apps/document-intelligence
uv run document-intelligence-eval --output reports/offline-metrics.json
# Explicit opt-in after configuring a provider and reviewing cost:
uv run document-intelligence-eval --live --output reports/live-metrics.json
\`\`\``;

const SECTIONS = [
  { id: "background", title: "Background" },
  { id: "contract", title: "Page analysis contract" },
  { id: "modes", title: "Four modes" },
  { id: "evidence", title: "Evidence & performance" },
  { id: "interface", title: "Interface" },
  { id: "downloads", title: "Downloads/exports" },
  { id: "evaluation", title: "Evaluation" },
  { id: "specs", title: "Specs & limits" },
] as const;

const SPECS = [
  {
    title: "architecture",
    text: "Analysis contracts, AI trust boundaries, evidence resolution, queue semantics, tenancy, and evaluation design.",
    href: `${REPO}/specs/architecture.md`,
  },
  {
    title: "operations",
    text: "Local and Compose setup, gateway identity, model limits, worker recovery, retention, and live evaluation.",
    href: `${REPO}/specs/operations.md`,
  },
  {
    title: "application source",
    text: "The independent uv workspace, FastAPI routes, worker, Alembic migrations, tests, fixtures, and reports.",
    href: REPO,
  },
  {
    title: "workbench frontend",
    text: "Typed API client, per-page analysis views, PDF evidence overlays, page-scoped chat, progress, and downloads.",
    href: `${REPO}/web`,
  },
];

export function DocumentIntelligenceArticle() {
  usePageMeta({
    title: "AI Document Intelligence Workbench",
    description:
      "Page-level PDF analysis: one AI call per page produces cited summaries, typed entities, and topics, plus page-scoped cited chat with exact parser-resolved evidence.",
    canonical: "/apps/document-intelligence",
  });
  const active = useScrollSpy(SECTIONS.map((section) => section.id));

  return (
    <>
      <header className="detail-header">
        <p className="kicker">&gt; apps / document-intelligence</p>
        <h1>AI Document Intelligence Workbench</h1>
        <p className="detail-lead">
          <strong>AI analyzes page by page, deterministic code verifies every citation,
          and partial results stay visible while the worker continues.</strong> One
          analysis call per page produces a summary, typed entities, and topics; a
          fourth mode adds page-scoped conversation with bounded history.
        </p>
        <div className="chips" aria-label="Technology stack">
          {["Document AI", "page-level analysis", "cited chat", "FastAPI", "Postgres", "React + TypeScript"].map((tech) => (
            <span key={tech} className="chip">{tech}</span>
          ))}
        </div>
        <div className="meta-links">
          <a className="chip-link" href={REPO} target="_blank" rel="noopener noreferrer">[source]</a>
          <a className="chip-link" href={`${REPO}/specs`} target="_blank" rel="noopener noreferrer">[specs]</a>
        </div>
      </header>
      <div className="story-layout">
        <nav className="rail" aria-label="App article sections">
          <span className="rail-label">index</span>
          {SECTIONS.map((section, index) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className={active === section.id ? "active" : ""}
              aria-current={active === section.id ? "location" : undefined}
            >
              <span className="rail-num">{String(index + 1).padStart(2, "0")}</span>
              {section.title.toLowerCase()}
            </a>
          ))}
        </nav>
        <div>
          <AppArticleSection
            id="background"
            index={1}
            title="Background"
            subtitle="a document workbench built around verifiable per-page answers, not opaque JSON"
            takeaway="The useful unit is a page-level result linked to exact source evidence—not an unverified model response."
          >
            <LazyFlowDiagram specId="app-document-intelligence-architecture" />
            <div className="prose">
              <p>
                This standalone application turns a born-digital PDF into per-page,
                citation-backed analysis: the engineering that makes model output
                usable lives in strict contracts, exact citations, tenant isolation,
                leased background jobs, and page-by-page progress.
              </p>
              <ul>
                <li>One Pydantic AI call per page produces that page's summary, entities, and topics.</li>
                <li>A separate tool-free agent powers page-scoped conversation with bounded history.</li>
                <li>PyMuPDF, not the model, owns pages and bounding boxes.</li>
                <li>Postgres, API, worker, React UI, fixtures, and evaluations ship together.</li>
              </ul>
            </div>
          </AppArticleSection>

          <AppArticleSection
            id="contract"
            index={2}
            title="Page analysis contract"
            subtitle="one structured-output call per page over delimited, untrusted text"
            takeaway="Each page is analyzed independently, so results appear page by page and one slow page never blocks the document."
          >
            <div className="prose">
              <p>
                The model receives a single page of text wrapped in untrusted-document
                delimiters—no tools, no repository or blob access, no path to storage or
                persistence. Documents may contain tables and images: table text is included
                in the page context, and image regions are counted and flagged. A page
                without an embedded text layer is flagged; raster OCR is never silently
                claimed when it is unavailable.
              </p>
              <p>
                Entity types use a controlled taxonomy mirrored by the workbench controls;
                topic labels stay open and concise. Bounded retries and request/token
                limits constrain each run; provider budgets remain an operational control.
              </p>
            </div>
            {renderMarkdown(CONTRACT_SNIPPET)}
            {renderMarkdown(AGENT_SNIPPET)}
          </AppArticleSection>

          <AppArticleSection
            id="modes"
            index={3}
            title="Four modes"
            subtitle="three analysis lenses per page plus one page-scoped conversation"
            takeaway="Summary, Entities, and Topics are three views over the same per-page analysis; Chat answers questions about the selected page only."
          >
            <div className="prose">
              <ul>
                <li><strong>Summary:</strong> a page summary plus evidence-backed key points.</li>
                <li><strong>Entities:</strong> literal mentions, normalized names, types, and citations.</li>
                <li><strong>Topics:</strong> open, concise labels for the page with supporting passages.</li>
                <li><strong>Chat:</strong> page-scoped conversation over the selected page with bounded history and exact citations.</li>
              </ul>
              <p>
                Because all three analysis views come from one call, they stay coherent
                with each other. Chat is deliberately scoped to the page in view: it
                receives that page's parsed text and a bounded history window, and it can
                discuss nothing else.
              </p>
            </div>
            <LazyFlowDiagram specId="auto-app-document-intelligence-1" />
          </AppArticleSection>

          <AppArticleSection
            id="evidence"
            index={4}
            title="Evidence & performance"
            subtitle="parser-resolved citations with page-by-page progress"
            takeaway="A missing, ambiguous, or fabricated citation becomes a visible validation error; completed pages stay visible while the worker continues."
          >
            <div className="prose">
              <p>
                Every summary key point, entity, and topic carries verbatim quotes.
                Model-supplied coordinates are discarded: each quote is matched after a
                unicode compatibility fold (ligatures, curly quotes, dashes) across the
                page's text spans, extracted table lines, and image placeholders. A quote
                occurring on several passages resolves to the first whole-passage match
                and surfaces a warning; a quote matching nothing stays a visible error
                on that page. The literal entity mention must occur in its cited quote,
                and only matching PyMuPDF-owned geometry contributes page and
                bounding-box coordinates.
              </p>
            </div>
            {renderMarkdown(EVIDENCE_SNIPPET)}
            <div className="prose">
              <ul>
                <li><strong>Partial pages:</strong> analysis progress is page-by-page; finished pages are visible while the worker continues.</li>
                <li><strong>Tables and images:</strong> table text feeds the page context; image regions are counted and flagged on the page.</li>
                <li><strong>No silent OCR:</strong> pages without an embedded text layer are flagged, not quietly passed to raster OCR.</li>
                <li><strong>Bounded execution:</strong> expiring leases, owner-checked heartbeats, bounded retries, and <code>FOR UPDATE SKIP LOCKED</code>.</li>
              </ul>
            </div>
          </AppArticleSection>

          <AppArticleSection
            id="interface"
            index={5}
            title="Interface"
            subtitle="the source PDF and every page result stay in one analysis workspace"
            takeaway="Selecting a summary point, entity, topic, or chat answer reveals its exact source passage."
          >
            <div className="app-media-grid">
              <AppScreenshot
                name="document-intelligence-summary.png"
                alt="Per-page cited summary, typed entities, and topics beside the source PDF"
                caption="Summary, Entities, and Topics are three lenses over the same per-page analysis."
              />
              <AppScreenshot
                name="document-intelligence-qa.png"
                alt="Page-scoped cited chat with exact source citations"
                caption="Page chat answers questions about the selected page with parser-resolved highlights."
              />
            </div>
            <div className="prose">
              <p>
                The React client renders the PDF with <code>pdfjs-dist</code> and overlays only
                backend-resolved coordinates. Summary, Entities, Topics, and Chat are the
                primary views; a per-page progress rail shows which pages are done, running,
                or failed.
              </p>
              <ul>
                <li>Completed pages render as soon as the worker finishes them.</li>
                <li>Loading, unresolved evidence, provider failure, and retry states remain explicit.</li>
                <li>Chat history is bounded per page and never bleeds across pages.</li>
              </ul>
            </div>
          </AppArticleSection>

          <AppArticleSection
            id="downloads"
            index={6}
            title="Downloads/exports"
            subtitle="full-document and selected-page reports off the server record"
            takeaway="Download the complete analysis or just the page in view, as JSON or Markdown."
          >
            <div className="prose">
              <p>
                Reports render from the server-side analysis record: what was analyzed is
                what downloads. Both formats carry the page structure, so a downloaded
                report reads the same way as the workbench.
              </p>
              <ul>
                <li><strong>Full analysis:</strong> every completed page in one file, as JSON or Markdown.</li>
                <li><strong>Selected page:</strong> the page in view only, same two formats.</li>
                <li><strong>Honest state:</strong> pages still queued or failed at export time are listed, never silently omitted.</li>
              </ul>
            </div>
          </AppArticleSection>

          <AppArticleSection
            id="evaluation"
            index={7}
            title="Evaluation"
            subtitle="page-level scorecards with evidence, latency, usage, and cost"
            takeaway="Offline fixtures verify the application path; only an executed provider run supports live-quality claims."
          >
            <div className="prose">
              <p>
                The mixed-document harness scores analysis at page level against committed
                non-sensitive references and retains per-page misses. Its report records
                provider/model, prompt and schema versions, dataset revision, run errors,
                and the exact evaluation method. There is no review step in the product, so
                the harness reports no human correction rate; classification metrics are
                gone with the retired document-level classifier.
              </p>
              <ul>
                <li>Summary key-point coverage and citation support, per page.</li>
                <li>Entity precision, recall, F1, and type accuracy, per page.</li>
                <li>Topic label quality against page-level references.</li>
                <li>Chat answer correctness and citation support; unresolved evidence, latency, usage, and cost.</li>
              </ul>
              <p>
                The small synthetic corpus is a regression suite, not a universal accuracy
                claim. Deterministic offline output proves the fixture-to-analysis-to-evidence
                path without credentials. Live reports are generated only after an explicit
                provider opt-in, and live numbers are re-measured on each run.
              </p>
            </div>
            {renderMarkdown(EVAL_SNIPPET)}
            <div className="prose">
              <p>
                <strong>Measured with <code>kimi-for-coding</code> on the committed synthetic corpus
                (2026-11-08): chat answer accuracy 1.00 with reference citations 1.00, evidence
                resolvability 1.00, entity F1 0.68, topic F1 0.50, zero page failures; per-page
                misses are reported in the JSON.</strong>
              </p>
              <p>
                <a href={`${REPO}/reports/live-metrics.json`} target="_blank" rel="noopener noreferrer">inspect the current live report →</a>{" · "}
                <a href={`${REPO}/reports/offline-metrics.json`} target="_blank" rel="noopener noreferrer">offline verification →</a>{" · "}
                <a href={`${REPO}/src/document_intelligence/evals/analysis_runner.py`} target="_blank" rel="noopener noreferrer">read the harness →</a>
              </p>
            </div>
          </AppArticleSection>

          <AppArticleSection
            id="specs"
            index={8}
            title="Specs & limits"
            subtitle="the source, operating contract, and adoption boundaries travel with the application"
            takeaway="The template is ready to adapt; representative evaluation still belongs to each rollout."
          >
            <div className="app-spec-grid">
              {SPECS.map((spec) => (
                <Card key={spec.title} className="app-spec-card">
                  <span className="study-block-label">spec</span>
                  <h3>{spec.title}</h3>
                  <p>{spec.text}</p>
                  <a href={spec.href} target="_blank" rel="noopener noreferrer">open spec →</a>
                </Card>
              ))}
            </div>
            <div className="prose">
              <p><strong>Production handoff checklist</strong></p>
              <ul>
                <li>Authenticate at the gateway, strip client identity headers, and inject secrets through a manager.</li>
                <li>Run Postgres, migrations, API, and worker separately; test database and blob restores.</li>
                <li>Use private encrypted storage and explicit retention/legal-hold policies.</li>
                <li>Set provider budgets and acceptance thresholds for the actual document population.</li>
                <li>Validate on representative documents from the real population before rollout.</li>
              </ul>
              <p>
                <strong>Limits:</strong> committed fixtures are synthetic and born-digital.
                The app does not claim raster OCR, handwriting support, universal accuracy,
                straight-through processing, ROI, or unattended accuracy. Pages without an
                embedded text layer are flagged instead of silently OCR'd, and a real
                rollout still needs representative data plus a security/privacy review.
              </p>
              <p>
                <a href={`${REPO}/README.md`} target="_blank" rel="noopener noreferrer">start with the app README →</a>
              </p>
            </div>
          </AppArticleSection>
        </div>
      </div>
    </>
  );
}
