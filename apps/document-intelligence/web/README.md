# document-intelligence web

Standalone Vite + React + TypeScript frontend for the document-intelligence FastAPI
service. The workbench analyzes PDFs page by page: each selected page offers a cited
summary, typed entities, topics, and a conversation scoped to that page. It renders
original PDFs with `pdfjs-dist` and overlays only backend-resolved
`Evidence.page` / `Evidence.bbox` values.

## Run

From this directory:

```bash
npm ci
npm run dev
```

Vite listens on `http://localhost:4323` and proxies `/documents`, `/health`, and
`/ready` to `http://localhost:8001`. For end-to-end uploads, start the real API,
worker, migration, and Postgres stack from `apps/document-intelligence`:

```bash
docker compose -f infra/docker-compose.yml up --build
```

The bare uvicorn quickstart does not process queued jobs. Set
`VITE_API_PROXY_TARGET` to change the development proxy or `VITE_API_BASE_URL`
for a different API origin. `VITE_DEV_TENANT` and `VITE_DEV_ACTOR` default to
`demo` and `developer`; use an isolated tenant for clean media captures.

Development requests include those two headers. They are not added by production
builds. Production must put the app behind the same authenticated gateway/tenant
boundary as the API.

The top-bar `dark` / `light` control switches the full workbench theme. The
selection is stored in browser-local storage under `document-intelligence-theme`;
no theme data is sent to the API.

The upload panel loads synthetic PDFs from `public/fixtures/`. Offline analysis
is a functional baseline, **not live-model accuracy** or a live evaluation.
Regenerate backend and browser fixtures together with
`uv run python scripts/generate_fixtures.py` from the app root.

## Checks

```bash
npm test
npm run lint
npm run build
```

## Media capture

With the Compose API/worker running, install Chromium inside this workspace and
run the committed Playwright capture:

```bash
PLAYWRIGHT_BROWSERS_PATH=./.playwright-browsers npx playwright install chromium
VITE_DEV_TENANT=document-media npm run dev -- --port 4330
# In another shell from web/:
DOCUMENT_INTELLIGENCE_UI_URL=http://127.0.0.1:4330 \
DOCUMENT_INTELLIGENCE_DEV_TENANT=document-media \
PLAYWRIGHT_BROWSERS_PATH=./.playwright-browsers \
node scripts/capture-demo.mjs ../../showcase-web/public/apps
```

The script uploads only the synthetic CV, waits for the real worker, and captures
the page summary/evidence view and the cited per-page conversation. Browser
downloads and media artifacts are ignored by Git.

## Contract notes

- All analysis payloads use `PageAnalysisResult` with `schema_version:
  page-analysis-v1`. Runtime validators reject malformed responses and retired
  `analysis-v1` extraction payloads before they reach the UI.
- `DocumentRecord.status` is one of `uploaded | processing | completed | failed`.
  Polling merges partial per-page results in stable page order and never touches
  chat history or the selected page.
- Citation clicks only reveal backend-resolved evidence; there is no browser-side
  text editing, correction, or approval flow.
- Page conversation history is kept in memory per document/page within a bounded
  window (the last 40 turns); only the last 20 turns are sent to
  `POST /documents/{id}/pages/{page}/chat`, and chat never mutates the stored
  analysis.
- JSON and Markdown downloads come from the backend's canonical export endpoints
  (`analysis/export` and `pages/{page}/export`); they download analysis, not the
  PDF. Page exports stay disabled until that page's analysis exists.
- Duplicate uploads open the existing document and explicitly report that no new
  job was queued.
