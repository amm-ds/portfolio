# Pre-Publish Review — 2026-10-14

State of the platform before opening the site to the public: three independent audits
(backend/security, frontend/coherence, content/consistency), their fixes, and the
state of every project and its roadmap.

## Executive summary

**Verdict: publishable after this wave.** The audits found one critical security bug
(confirmed path traversal — now fixed and re-tested), one deployment-risk decision
(public LLM proxy — now env-gated, fail-closed, and removed from the public UI), and a
set of content staleness issues (now corrected against live metrics). Code quality was
rated strong across the board; the fixes below are the difference between "good repo"
and "public-ready repo".

## Security audit (backend) — findings & resolutions

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| A-1 | **High** | Path traversal in the SPA catch-all — `/../../../pyproject.toml` served with 200 (PoC-confirmed; uvicorn decodes `%2f`, nothing normalized dot segments) | Paths resolved and confined to the build dir (`resolve()` + `is_relative_to`); PoC re-run returns the app shell, not the file |
| A-2 | **High** (with keys) | `/rag/chat*` = unauthenticated LLM cost proxy; no opt-in, no prompt cap | Routes register only when `RAG_CHAT_ENABLED=1` (fail closed); `question` capped at 4000 chars; demo removed from the public UI |
| A-3 | Medium | Forecast endpoint reloaded a 6.5 MB artifact per request; unbounded feature dict | Artifact cached after first load; features capped at 64 keys; zone validated before scoring |
| A-4 | Low | Raw exception text (absolute paths) in 503 details | Generic client messages; details logged server-side |
| A-8 | Medium | Container ran as root | `USER app` in the Dockerfile |
| A-9 | Low | No pid format validation; agent-cache race; duplicate import | `^\d{2}-[a-z0-9-]+$` validation; `anyio.Lock`; imports cleaned |

Verified after fixes: traversal PoC dead, `pid=".."` → 404, chat routes absent by
default (405), forecast endpoint still serves (JFK zone: 223.8 pickups, p90 251.8).

## Frontend audit — findings & resolutions

| Area | Finding | Resolution |
|---|---|---|
| Critical-for-launch | Contact email placeholder | Centralized `SITE_EMAIL` in `src/config.ts` (one variable to change) |
| Decision | RAG demo in discoverability limbo + mock-disclosure credibility risk | Removed from the public site entirely (route/page/banner/meta); API stays env-gated for private demos |
| High | 4.8 MB plotly chunk on first case-study visit | Dynamic import deferred until the figure nears the viewport (IntersectionObserver) |
| Medium | RAGChat h1 broke the title system; catch-all rendered Home for typos; dead CSS (~70 lines); no `:focus-visible`; accent-glow repeated 7×; card/table patterns duplicated; format helpers duplicated; nav landmark noise; empty-list state missing | All fixed: 404 page, CSS cleanup + vars + utilities, dedupe, focus styles, empty states |
| Pass | Visual coherence, heading order, contrast (AA), reduced-motion, loading/error states, lazy chunks, zero TODOs/console.logs | — |

**Projects page improved**: cards now grouped under Flagships / Working showcases,
each with a live key number fetched from its metrics (nothing rendered until data
loads), status badges, techniques, and description.

## Content audit — findings & resolutions

| Finding | Resolution |
|---|---|
| NSL-KDD story link 404'd (no registry card) | `docs/data-registry/nsl-kdd.md` created + index entry |
| Root README 06 row stale (19.08% pre-ALNS) | Now the real headline: ALNS 4.23%, 56 instances, floor 317% |
| Root README 05 stale (−89% ECE) | −95% (matches metrics/story/docs) |
| 01 docs latency diverged (4.2/5.0 ms) | Synced to metrics (3.7/7.2 ms) |
| 03 PR-AUC sentence carried ROC deltas | Corrected (+0.12 / +0.11) |
| Wave-era phrasing in public copy ("Wave 7 delivered…") | Scrubbed across docs + stories |
| 06 runtime rounding + negative-gap ordering | Corrected to metrics values, second-best example fixed |
| UK/US spelling drift | Normalized to US English in the flagged spots |

## State of projects

| # | Project | Status | Runs in metrics | Tests | Headline (current) |
|---|---|---|---|---|---|
| 01 | RAG agent | flagship | 15 | ~59 | recall@5 0.962 vs 0.038 random; −65% context cost; client-corpus onboarding + cost telemetry shipped |
| 02 | Demand forecasting | working | 6 (+UCI track) | ~40 | tuned GBM −41.1% MAE vs persistence; real-data track exposes where synthetic breaks (ridge < naives at 89% zeros; reconciliation pays) |
| 03 | Anomaly detection | working | 7 | 68 | residual features AUC 0.9999; adaptive streaming; NSL-KDD probe 0.882 |
| 04 | NLP classification | working | 7 | ~45 | 0.902 macro-F1 bounded; full-data path GPU-gated (20k evidence: 0.927); seed study 0.8910 ± 0.0042 |
| 05 | Churn | working | 5 | 43 | cost-aware HPO picks the true winner (282, CI [−237, −87] sig.); isotonic −95% ECE; CRM onboarding |
| 06 | Routing (VRPTW) | working | 4 (+per-instance) | ~45 | **ALNS 4.23% mean gap, 56/56 vs 2-opt, all 56 instances** |
| 07 | Mobility | flagship | 6 (+transfer) | 45 | GBM −28.4% vs naive; p90 90.8% coverage; **live forecast endpoint**; green-taxi transfer study |

Workspace totals: ~370 tests at ~97% coverage (libs ≥80% enforced), ruff/mypy clean,
mkdocs strict green, reproducible web build.

## Roadmap state (what actually remains)

Fully closed: 03, 04, 07. Remaining items are deliberately final:

- **01**: interactive deployment demo; live-mode telemetry accumulation (needs a live provider).
- **02**: calibrated intervals for intermittent demand; full MinT covariance (waits for a deeper real hierarchy); returns-aware demand.
- **05**: real-data CRM track (engagement-dependent); broader model comparison.
- **06**: hierarchical objective (multi-echelon constraints).
- **Platform**: geo choropleth (needs geopandas); causal weather estimates (needs causal design).

## Publishing checklist

- [x] Path traversal closed (PoC re-tested)
- [x] LLM proxy env-gated, fail-closed; demo off the public site
- [x] Non-root container user
- [x] Contact email centralized and filled
- [x] Numbers synchronized across README/stories/metrics
- [x] Dead CSS removed; a11y basics (focus-visible, AA contrast, reduced motion)
- [x] Projects page: grouped cards with live key numbers
- [ ] **User action**: confirm `amm.datascience@gmail.com` (change in one variable: `apps/showcase-web/src/config.ts`)
- [ ] **User action**: DNS/domain decision — the site serves at `:8080` locally; public hosting options: (a) the Docker image on any VPS, (b) a static export for a static host (figures/metrics/stories could be baked at build time — a small follow-up), (c) keep GitHub Pages as the public site and the app as the demo layer
- [ ] Optional follow-ups: server-side rate limiting if the forecast endpoint is publicly hosted; figure PNG snapshots for README embedding (kaleido)
