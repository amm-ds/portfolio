# Full Repo Review — 2026-11-06

Refresh of the same-day review after the backend and stylesheet seams landed.
Scope: backend, shared libraries, frontend, infrastructure, documentation, and
presentation. The review was read-only except for the docs-gate DVC-output fix,
its convention note, and this report. No training or evaluation pipeline was
run; the 02 full-panel re-run remains independent and active.

## Executive verdict

The repository has a strong public-portfolio and small-production-service
foundation. It does **not** need a rewrite, another framework, or further
immediate decomposition of `showcase_api.main.py`. The next highest-value work
is a short correctness and release-hardening wave, followed by restrained UI
legibility and state-management refinements.

No P0 issue was found. Publication should wait for the P1 items below:
request-validation correctness, production CSP for interactive artifacts,
mobile diagram legibility, broken/weak CI signals, and the unresolved public
DNS cutover.

## Verified strengths — preserve these

- **Backend:** typed manifests and inference contracts, consistent request IDs
  and error envelopes, bounded model execution, body/rate limits, live budget
  and kill switch, fail-closed optional features, and broad concurrency and
  route regression tests.
- **Shared code:** `portfolio-core` and `portfolio-eval` genuinely reuse
  configuration, schemas, DQ, metrics, time-CV, plotting, reporting, and demo
  contracts. Strict mypy covers the shared libraries and most project packages.
- **Frontend:** a coherent terminal identity, reusable cards/tables/workbenches,
  route-level splitting, viewport-gated Plotly, static-first Mermaid, keyboard
  React Flow nodes, figure data-table alternatives, and good text contrast.
- **Infrastructure:** locked uv/npm dependencies, digest-pinned production
  images/actions, non-root/read-only/capability-dropped runtime, Caddy-only
  public ingress, dependency audit, CodeQL, a 13-project CI matrix, nightly
  property/soak/repro jobs, and explicit manual deployment/rollback docs.
- **Evidence:** short copy is single-sourced across 52 surfaces; story language,
  demo contracts, generated registries, dataset cards, and committed metrics
  make public claims unusually auditable.

## P1 — correctness and release blockers

### 1. Custom request validators can turn a client error into a 500

`apps/showcase-api/src/showcase_api/main.py:98-109` serializes
`RequestValidationError.errors()` directly. Pydantic model-validator entries
can contain `ctx.error: ValueError`, which is not JSON serializable. A routing
request with `due_time < ready_time` reproduced the generic 500 response.
The validators are in
`projects/06-routing-optimization/src/routing_optimization/schemas.py:40-68`.

**Proposal:** serialize through `jsonable_encoder` with explicit exception
handling, preserve the existing envelope, and add regressions for invalid time
windows, duplicate IDs, and non-consecutive IDs. In the same small boundary
pass, reject NaN/infinity on public numeric request models and log only error
locations/types/counts rather than complete invalid input values.

### 2. Production CSP blocks scripts in published interactive artifacts

`deploy/Caddyfile:17-30` has no `script-src`, so `default-src 'self'` applies.
The HTML reports and standalone figures use inline bootstrap code and CDN
assets (`libs/portfolio-eval/src/portfolio_eval/report.py:41-98`,
`libs/portfolio-core/src/portfolio_core/plotting.py:181-185`). This affects
`srcDoc` reports, HTML figure fallback, and the default FastAPI docs.

**Proposal:** prefer self-hosted report assets with no inline bootstrap. Until
then, use a narrowly scoped CSP for trusted artifact routes and real iframe
sandboxing. Add a production-mode browser smoke test; curl cannot detect a CSP
that blocks JavaScript.

### 3. Mobile React Flow diagrams are technically present but unreadable

`FlowCanvas` fits the whole graph into a narrow viewport with `MIN_ZOOM = 0.1`
(`apps/showcase-web/src/components/diagrams/FlowDiagram.tsx:224-238,327-340`).
The 350 px evidence image `artifacts/diagram-refinement/04-mobile.png` reduces
node labels to a few pixels. Several diagram/workbench labels are only
0.58–0.68 rem, and diagram controls are 30 px.

**Proposal:** below 640 px, use a vertical layout or an accessible node-outline
fallback. The smaller alternative is initial 0.6–0.75 zoom plus panning rather
than fitting the full horizontal graph. Establish a 0.75 rem secondary-label
floor and coarse-pointer targets around 48 px. Keep the desktop canvas and
inspector.

### 4. CI is not currently a reliable green release signal

- Latest main CI (`884a6eb`) failed only at the docs link gate. DVC-generated,
  git-ignored outputs were treated as broken links. The local fix now passes;
  it must be committed and verified in CI.
- The last three nightly runs failed `weekly-dvc-repro`. Logs show `uv run`
  recreating the workspace environment from a project directory and then DVC
  failing with missing modules. Use the already-synced environment (`--no-sync`
  or an equivalent single-environment contract) instead of re-resolving in the
  project subdirectory.
- Nightly `notify` also failed because `gh issue create` ran without a checkout
  (`.github/workflows/nightly.yml:373-406`). Add checkout or pass an explicit
  repository without depending on a git worktree.
- Nightly's matrix still omits projects 12 and 13 even though PR CI includes
  them (`.github/workflows/nightly.yml:75-121`).
- The isolated `apps/agent-chat` suite has no CI job. Its own lockfile/venv are
  correct; add an explicit isolated job rather than folding it into root CI.
- ESLint is locally clean but non-blocking; axe and lychee are also
  non-blocking (`.github/workflows/ci.yml:142-220`). Make ESLint blocking now,
  fix the committed axe landmark findings, then make axe blocking.

### 5. The public launch identity still has no address records

A fresh DNS check returned no A, AAAA, or `www` CNAME for
`alejandromerida.dev`. The existing docs site remains reachable on GitHub
Pages, but the custom-domain launch cannot work until DNS is published.

**Proposal:** treat DNS, canonical URLs, sitemap/robots, Open Graph metadata,
and the production smoke test as one cutover change. Do not flip only some of
these surfaces.

## P2 — small engineering fixes with real payoff

### Backend and shared libraries

- **Disconnect handling:** `middleware.py:127-136` continues on every non-
  `http.request` message. Return on `http.disconnect`; add a scripted ASGI
  receive-sequence test.
- **Budget overrides:** `portfolio_core/llm_budget.py:198-216,281-296` drops
  supplied settings when recording cost, so environment rate-card overrides
  can be ignored by actual metering. Thread settings through and test the full
  path.
- **Cold-start bounds:** `showcase_api/serving.py:49-54` has no per-artifact
  lock; artifact loading occurs before endpoint semaphores/timeouts. Prevent
  duplicate cold loads and strengthen readiness to check required bundle
  loadability, including mobility's green bundle.
- **Log hygiene:** `middleware.py:68-71` logs the raw rate-limit key (client
  IP), contrary to the no-raw-IP policy. Remove or hash it.
- **Artifact contracts:** validate that demo payload JSON is an object and
  confine `PayloadRef.path` to the project directory
  (`portfolio_core/demo.py:51-56`, `showcase_api/main.py:414-434`).
- **Graceful container shutdown:** root `Dockerfile:91` uses `sh -c` without
  `exec`. Keep environment expansion but `exec uvicorn` so signals reach the
  server directly, matching FastAPI's container guidance.
- **API versioning:** commit an OpenAPI/JSON-Schema golden and add explicit
  response models where useful. Do not introduce a breaking `/v2` merely for
  appearance.

### Frontend correctness and performance

- **Hash navigation:** `RouteAnnouncer.tsx:11-24` watches only `pathname` and
  always scrolls to top. Honor `location.hash` after lazy route mount; only
  scroll to top when no hash exists. Test `/glossary#baseline` and
  `/projects#demos`.
- **Outermost crash fallback:** `TopLevelErrorBoundary.tsx:24-36` renders a
  React Router `<Link>` outside `BrowserRouter`. Use a plain `<a href="/">`.
- **Missing vs failed:** `ProjectDetail.tsx:148-175` and `ReportView.tsx:40-58`
  collapse transport/500 failures into “not published” states. Use explicit
  `loading | ready | missing | error | snapshot` states with retry.
- **Request fan-out:** every `ProjectCard` fetches full metrics. Put one selected
  headline in the startup-computed project index or add a compact batch
  endpoint. Keep full metrics on detail pages.
- **Report probes:** replace full-report GET availability checks with HEAD or
  project metadata. Lazy-load `ProjectsIndex`, and gate figure JSON fetches on
  the same viewport signal as Plotly itself.
- **Accessibility:** make the nav root a `<header>`, avoid repeated identical
  complementary landmarks, focus/announce the first contact-form error, and
  correct nested card heading levels. Add mobile/tablet browser checks.

## Presentation refinements — polish, do not redesign

The existing terminal system is the differentiator. The opportunity is better
reading rhythm and interaction feedback, not more colors, glass effects, or
animation.

1. **Restore a prose measure.** Cap only hero/detail/story prose around
   68–78ch. Keep cards, tables, dashboards, and reports fluid and wide.
2. **Tighten Home's composition.** Reduce the hero's 68vh minimum/dead space so
   “where to go” sits closer to the terminal; retain the wider terminal and
   current title/color hierarchy.
3. **Stop truncating identity content.** Let framework/cloud names wrap or give
   tiles a slightly wider minimum. Use normal case for long dataset metadata;
   reserve uppercase tracking for short labels.
4. **Unify interaction states.** Reuse one focus/hover/active treatment and a
   small spacing/token scale. Add restrained 120–160 ms transitions only where
   they clarify response, with one shared reduced-motion rule.
5. **Make evidence navigable.** Add one restrained related-case-study link per
   service offering after hash navigation is fixed. Keep services generic; the
   link is evidence, not sales copy.
6. **Improve chart legibility before adding chart types.** Lighten the forecast
   violet for non-text contrast, preserve dashed/bold series encodings, and
   prioritize mobile React Flow over new diagram dependencies.
7. **Measure experience.** Add a lightweight production Web Vitals check:
   LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at the 75th percentile. Keep the
   existing no-third-party-analytics posture unless separately approved.

References used for these recommendations:

- [web.dev — Web Vitals](https://web.dev/articles/vitals) and
  [accessible tap targets](https://web.dev/articles/accessible-tap-targets).
- [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility):
  retain keyboard focus, selection, and screen-reader behavior in any mobile
  fallback.
- [FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/):
  direct process signals, explicit proxy boundaries, and memory-aware worker
  decisions. The current single-process shape remains appropriate.
- [Brittany Chiang](https://brittanychiang.com/) for clear proof-of-work
  hierarchy, [Rauno](https://rauno.me/) for restraint and consistency, and
  [Josh Comeau](https://www.joshwcomeau.com/) for interactive explanation that
  serves the content rather than decorating it.

## Recommended implementation waves

### Wave 1 — correctness, privacy, and trustworthy CI

Fix validation serialization, disconnect handling, budget settings, raw-IP /
invalid-input logging, and docs-gate DVC outputs. Add focused regressions.
Repair nightly environment reuse and notification checkout; add 12/13 and
agent-chat coverage; make ESLint blocking.

### Wave 2 — user-visible robustness and accessibility

Fix hash scrolling, the outer error boundary, explicit async error states,
landmarks, contact-form focus, mobile diagrams, label sizes, and coarse-pointer
targets. Add 390 px and 768 px browser tests and then make axe blocking.

### Wave 3 — production cutover

Resolve CSP/self-hosted artifact assets, add a production browser smoke and an
external health/TLS probe, commit the API schema golden, verify graceful
shutdown, and perform the atomic DNS/metadata cutover.

### Wave 4 — restrained visual and performance polish

Apply prose measures, Home spacing, framework/metadata wrapping, unified
interaction tokens, batch headline metrics, HEAD report probes, lazy projects
route, viewport-gated figure data, and Web Vitals checks. Screenshot Home,
Projects, Services, one case study, one report, and one diagram at desktop and
mobile widths.

## Explicitly not recommended

- No backend rewrite or further `main.py` split without a new behavioral seam.
- No new CSS framework, component library, animation library, or diagram
  library for this wave.
- No multi-worker/Kubernetes/Redis topology before measured load requires it;
  current in-process limits are documented single-process guards.
- No blanket dependency-major upgrade mixed into these fixes. React/Vite/
  FastAPI upgrades deserve separate, audited changes.
- No public analytics or expanded RAG exposure by default.

## Verification recorded in this pass

- `uv run python scripts/check_docs.py` — **PASS** after the DVC-output fix.
- `uv run ruff check scripts/check_docs.py` and format check — **PASS**.
- `uv run python scripts/lint_story_language.py` — **PASS**, 13 stories, 0
  errors/warnings.
- `npm run lint` in `apps/showcase-web` — **PASS**.
- `uv run mkdocs build --strict` — **PASS**; existing nav informational notices
  remain, plus Material's forward-looking MkDocs 2.0 warning.
- `git diff --check` — **PASS**.
- Latest main CI failure was inspected; three recent nightly failures and their
  job logs were inspected directly.

The full Python/web suites were intentionally not rerun while the long 02
forecasting job is active. The 02 result must be judged by its adoption gate
when it completes; no forecasting result is changed by this review.
