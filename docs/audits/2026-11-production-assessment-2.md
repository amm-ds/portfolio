# Production Assessment — Pass 2 — 2026-11-04

Second-pass whole-repo audit, one day after
[`2026-11-production-assessment.md`](2026-11-production-assessment.md) (pass 1).
Since pass 1 the repo absorbed nine heavy change rounds: the visible-conclusions
platform change, template passes on all ten stories, the wave-31/32 M5
full-panel migration (02), a 03 experiment re-run (rank-average ensemble), UI
refinements, and a new scheduled drift-observatory workflow. Branch audited:
`main`. Read-only investigation except for this report; one disclosed exception:
running `scripts/axe_check.mjs` regenerates `reports/axe.json` in place (its
normal behavior), so that snapshot now reflects the 2026-11-04 run reproduced
below rather than the pass-1 snapshot.

**Scores at a glance**

| Dimension | Pass 1 | Pass 2 | One-line justification |
|---|---|---|---|
| Code quality | 9/10 | **8.5/10** | All gates green (933 project tests, mypy 164 files, ruff 406 files, web 350/350) and m5_full is exemplary, but a new real logic bug ships in `lib/delta.ts` (false baselines render cross-metric "+1689%" deltas on 01's public page) with a test that enshrines the wrong expectation. |
| Documentation | 8/10 | **8/10** | Playbook/compose-comment/docx findings fixed; README/docs reconcile to the cent after both result waves; held back by the still-dead launch domain and a RELEASE-NOTES changelog that omits the flagship M5 full-panel change. |
| Infra | 8/10 | **8/10** | New drift-observatory workflow and a clean eslint tree are real gains; held by still-non-blocking eslint/axe/lychee gates (7 moderate axe violations live), no external uptime probe, and nightly determinism now validating the *legacy* 02 track. |
| Productization | 7/10 | **7/10** | Demo contract/static registry green against the new full-panel payload, artifacts tree documented; the launch identity is still unreachable, there is still no versioned API contract, and the delta bug is visible on public project pages. |

No P0 findings. The engineering remains release-grade; the delta-audit found one
new public-facing correctness bug (P1) and one mis-aimed nightly proof (P1), plus
a set of P2 staleness items typical of heavy content waves.

---

## 1. Pass-1 fix state — all 16 findings

Legend: ✅ resolved · ◐ partial · ❌ unresolved · ◌ unchanged-by-design.

### Code quality

**◐ CQ P2-1 — Supported pytest parallelism still undocumented.**
`pyproject.toml:86-91`'s comment was rewritten ("Long-running per-project splits
… are handled by the CI matrix cell selection; the nightly workflow runs the
entire suite") but still never states that the monolithic/per-project runs are
validated at `-n 2` only — the actual guard requested. CI itself pins `-n 2`
(`ci.yml:270`, `nightly.yml:114`). All ten suites pass locally at `-n 2` (§4),
so the exposure remains a future "speed up CI" footgun.

**◐ CQ P2-2 — 08's scaffold test still tautological; 04's evaluate boundary now
has tests.**
`projects/08-inference-serving/tests/test_scaffold.py:1-4` is unchanged
(`assert inference_serving is not None`). 04 has boundary tests at the
evaluate/HPO surface (`tests/test_evaluate.py`, `test_hpo.py`,
`test_epochs_probe.py` — same 78-test count as pass 1, so these likely
predate it); per-module coverage was not re-measured this pass; suite total
measures 65 % (`--cov=src`, §4) with no per-project floor by design
(`ci.yml:265-276`).

**✅ CQ P2-3 / DOC P2-4 — Playbook no longer overstates pre-commit.**
`docs/engineering-playbook.md:7-11` now reads "mypy strict on `libs/*`; typed
function signatures everywhere" (Standard 1) and reserves "enforced by
pre-commit and CI" for ruff (Standard 2), which is true. The pre-commit hook
remains libs-only (`.pre-commit-config.yaml:13`) — acceptable, since the doc now
matches the mechanism.

**❌ CQ P2-4 — Dependency pins unchanged; drift persists.**
`uv.lock` is byte-identical in the audited packages to pass 1 (fastapi 0.143.0
vs PyPI 0.162.0, starlette 1.7.0 vs 1.10.0, pydantic 2.14.1 vs 2.14.2,
pydantic-ai 2.55.0 vs 2.65.0, transformers 5.19.0 vs 5.22.1, torch 2.14.1 vs
2.15.0, polars 2.0.0 vs 2.1.0; PyPI re-checked 2026-11-04). No bump wave
happened. `uv lock --check` → resolved 333 packages, no changes. pip-audit is
still un-runnable in this environment (uvx venv creation dies with the same
host `ensurepip` SIGABRT as pass 1); the CI gate at `ci.yml:129-135` remains the
authoritative vulnerability check.

**✅ CQ P2-5 — Dead code effectively zero.**
Zero `TODO`/`FIXME`/`XXX`/`HACK` in any `src/` tree. The two pass-1 unpacks are
gone or benign by refactor: `mobility/geo.py:31` `cfg_key` is an intentional
`@lru_cache` discriminator parameter; 02's `evaluate.py` `_fold_mase_parts`
takes `y_val` as a used parameter now.

### Documentation

**❌ DOC P1-1 / PROD P1-1 — Launch identity still dead (single root cause).**
DNS re-checked 2026-11-04 against 1.1.1.1 and 8.8.8.8: `alejandromerida.dev`
still publishes **zero A/AAAA/CNAME** (Cloudflare NS only). Every default still
points there: `apps/showcase-web/src/config.ts:11`, `index.html:8,15-37`,
`public/robots.txt:4`, `public/sitemap.xml:2` (lastmod 2026-11-02),
`scripts/gen_sitemap.py:20`. The live surface remains
`amm-ds.github.io/portfolio/`. Also still outstanding: **DOC P2-2** —
`mkdocs.yml:3,42-43` SEO URLs remain on the GitHub Pages origin (internally
consistent; per pass-1 guidance both sides change together).

**✅ DOC P1-2 — `docsUrl()` fixed (residual: no copy-guard).**
`apps/showcase-web/src/pages/ProjectDetail.tsx:27-32` now builds
`${DOCS_URL}/projects/${num}-${slug}/` from config — the hardcoded origin is
gone, and the produced path matches the mkdocs route shape. The recommended
copy-guard assertion was **not** added: `src/__tests__/copy-guard.test.ts`
contains no origin check, and one brand string remains hardcoded at
`ProjectDetail.tsx:75` (fallback meta description "…the alejandromerida.dev
ML/AI engineering portfolio.") — brand usage rather than a URL, but it flips
with the same identity decision.

**✅ DOC P2-1 — "Mock provider" comment fixed.**
`docker-compose.yml:9-10` now reads "unconfigured, Project 01 uses local Ollama
and the RAG chat endpoints stay disabled — no mock provider, see .env.example /
DEPLOY.md", matching the documented behavior.

**✅ DOC P2-3 — Binary review report moved out of the docs tree.**
`artifacts/review/Portfolio_Review_Report_amm-ds.docx` left `docs/` for the
gitignored `artifacts/` tree, and the new `artifacts/README.md` records what
both sub-trees are (screenshot diagnostics; the archived external review). The
derived `docs/portfolio_audit_amm-ds.md` stays in `docs/` root with unique
content and remains mkdocs-excluded (`mkdocs.yml:34-36`).

### Infrastructure

**❌ INFRA P1-1 — No external monitoring yet.**
No probe/TLS workflow exists. The new `.github/workflows/drift-observatory.yml`
(Thursdays, macos-15 runner) scores the newest published TLC month against
07's pinned serving bundle and files an issue on regression — a genuine
observability gain, but it watches *model drift*, not the deployment (dead VPS /
expired TLS / full disk are still visitor-discovered).

**❌ INFRA P2-1 — eslint/axe/lychee still non-blocking; axe violations persist
(and the detail page gained one).**
`ci.yml:142` (eslint), `ci.yml:162` (axe), `ci.yml:205,215` (lychee) remain
`continue-on-error: true`. Live axe re-run on 2026-11-04 (vite dev + API, same
script as CI): 7 moderate violations over 6 routes — `region` on `/`,
`/projects`, `/glossary`, `/demos/churn-sandbox`, `/demos/forecast-workbench`,
plus `region` **and** `landmark-unique` on `/projects/05-ml-pipeline-churn`.
ESLint itself is now clean locally (0 problems), so the "make eslint blocking"
half is unblocked and trivially ready.

**◌ INFRA P2-2 — `.dvc/config` still 0 bytes.** By design (ADR-0003, documented
in RELEASE-NOTES); pass 1 required no action. Unchanged.

**❌ INFRA P2-3 — Hybrid-split note still missing.** `deploy/DEPLOY.md:9-11`
keeps the "future hybrid split" paragraph but still doesn't name the in-process
rate limiter, live-call budget, or IP-hash salt as components needing a shared
store in a multi-replica topology.

**◌ INFRA P2-4 — `dev-salt` default kept.** `middleware.py:192-226` unchanged;
pass 1 explicitly recommended keeping the WARNING + compose `:?` guard posture.
No change needed.

### Productization

**❌ PROD P1-1 — Launch identity unreachable** (same evidence as DOC P1-1).

**❌ PROD P1-2 — Still no versioned API contract artifact.**
`apps/showcase-api/tests/` contains only `test_api.py` (+ `__pycache__`); no
committed OpenAPI/JSON-Schema golden. The docker smoke still probes three
endpoints' key fields (`ci.yml:360-374`).

**◌ PROD P2-1 — LLM-dependent evidence boundary unchanged** (documented, with
committed run records; not actionable).

**◐ PROD P2-2 — Release ritual partially improved.**
`RELEASE-NOTES.md` gained a dated "Result updates since first publication
(2026-10-29, verified)" section (03/05/06/07/09 entries, each reconciling with
committed artifacts — spot-checked 03's `1,609 → 80` alerts and
`0.157 → 0.315` range-F1 against `reports/nab_tune.json` defaults: exact
match). But there is still no `make release` checklist target
(`Makefile:58-64` has `lint-ci` and `release-verify` only), and the section
**omits the biggest post-release result change — 02's M5 full-panel migration**
(see NEW-3). The Audits list also doesn't mention the 2026-11-03 assessment.

**❌ PROD P2-3 — Demo-payload determinism still 02-only, and now aimed at the
wrong track.** `nightly.yml:45-62` still byte-checks only
`reports_m5/{metrics,probabilistic,demo_payload}.json` via `evaluate-m5` /
`demo-payload-m5`. 05 was never added, and 02's canonical artifacts moved to
`reports_m5_full/` (`main.py:259-264`; workbench payload
`ForecastWorkbench.tsx:54`) — so the nightly proves byte-identity for the
*legacy subset track* while the headline full-panel metrics and the served
workbench payload have **no scheduled determinism proof at all** (see NEW-2).

**✅ PROD P2-4 — `artifacts/README.md` exists** and documents both
`playwright-m5/` (M5 full-panel diagnostics) and `review/` (archived external
review, superseded pointer).

**Tally: 6 resolved · 3 partial · 7 unresolved (8 counting DOC P2-2 separately
from the shared P1 root cause).** Everything the rounds touched got *better*;
nothing they touched reopened an old finding; the unresolved set is almost
entirely the pre-existing identity/monitoring/contract debt, plus two new
infra-content gaps (NEW-2, NEW-3).

---

## 2. Delta audit — what the rounds broke or left stale

### 2.1 New finding P1-1 — `lib/delta.ts` false baselines render wrong public deltas

`apps/showcase-web/src/lib/delta.ts:21` — `BASELINE_RE =
/naive|random|lag|majority|persistence/i` — matches any run name containing
those substrings, and `StoryMetricsTable.tsx` (the per-row delta table the
conclusions/results sections render) treats the first match as *the* baseline
for the whole table. `projects/01-rag-agent/story.yaml:262-270,301-306`
references `retrieval_random_chunks_200` — a random-*retrieval ablation arm*,
not a performance baseline. Reproduced against committed `reports/metrics.json`
(the exact computation `computeCallouts` performs):

- `retrieval_chunks_200` (recall@5 0.8308) renders **"+2600% vs
  retrieval_random_chunks_200"**,
- `retrieval_model_minilm_chunks_200` and `retrieval_rerank_on_chunks_200` —
  same +2600 %,
- `rag_agent` — headline metric is **faithfulness 0.5504**, the baseline value
  falls back to the baseline's headline (delta.ts:86-89, recall@5 0.0308), so
  the end-to-end row renders **"+1689% vs retrieval_random_chunks_200"** — a
  percent delta between two different quantities.

Every other project only matches true baselines (02 `naive_*`/`seasonal_naive`,
03/10 `random`, 04 `naive_majority`/`random_uniform`, 07 `naive_lag24`), so the
damage is confined to 01's two tables — but 01 is the flagship, the site brands
itself on metric honesty, and a reviewer can see "+1689%" on a public page.
Worse, `src/__tests__/delta.test.ts:9-13` asserts
`isBaselineRun("random_forest") === true`, enshrining the false positive.

**Fix (small):** (a) in `computeCallouts`, drop the cross-metric fallback
(delta.ts:86-89) — if the baseline has no value for the candidate's metric, the
delta is `null`, not the baseline's headline; (b) tighten baseline detection
(word-boundary anchors, or better an explicit per-story baseline declaration in
the story schema instead of name regexes); (c) flip the test to assert
`random_forest` is **not** a baseline and add a cross-metric no-delta case.

### 2.2 New finding P1-2 — Nightly determinism validates the legacy 02 track

The wave-31/32 migration made `reports_m5_full/` canonical
(`main.py:259-264`, figure resolution `main.py:284-308`, workbench payload
`ForecastWorkbench.tsx:54`, demo contract OK against
`reports_m5_full/demo_payload.json`). But `nightly.yml:45-62` still runs
`evaluate-m5` + `demo-payload-m5`, which write `reports_m5/` — the retained
subset-era track kept as a "CI anchor". Consequences: (a) the headline
full-panel metrics (the numbers README/docs/story all quote) have no scheduled
run-twice byte-identity proof; (b) the served workbench payload has none either;
(c) the legacy track's artifacts are what get re-uploaded as "nightly-m5-reports".
The pass-1 PROD P2-3 recommendation (add 05's payload to nightly) is also still
open on top of this.

**Fix:** switch (or rotate monthly, given ~12.9 h runtime —
`evaluation_metadata.json: runtime_seconds 46508.7`) the determinism job to
`evaluate-m5-full` + `demo-payload-m5-full` with `cmp` pairs against
`reports_m5_full/`, and add 05's `demo-payload` run-twice `cmp` as pass 1
suggested. If the legacy-subset nightly is deliberately a cheap proxy, say so in
nightly.yml's header comment — today nothing documents the mismatch.

### 2.3 New findings P2

**NEW-3 · RELEASE-NOTES stale on the flagship change.** The "Result updates"
section covers 03/05/06/07/09 but says nothing about 02's full-panel migration
(0.6161 official WRMSSE on 42,840 nodes) — the largest post-release result
change and the one every headline surface now quotes. The Audits list also
omits the 2026-11-03 assessment. One paragraph fixes both.

**NEW-4 · Axe snapshot drifted upward; gates still non-blocking.** 7 moderate
violations across 6 routes on 2026-11-04 (was: 1 on `/`); new
`landmark-unique` on `/projects/05-ml-pipeline-churn` (moderate, 1 node) —
plausibly introduced by the detail-page waves. ESLint is clean, so flip eslint
to blocking now; fix `region` on the two demo routes next; then schedule the
axe-blocking wave with a date, as the CI comments have promised twice.

**NEW-5 · Copy-guard residual.** Pass-1's recommended hardcoded-origin assertion
in `copy-guard.test.ts` was never added (DOC P1-2 core fix *did* land). One
brand string remains at `ProjectDetail.tsx:75`.

**NEW-6 · `/projects/{pid}/figures` list endpoint only sees `reports/figures`.**
`main.py:311-314` lists only the canonical reports dir; for 02 that is the UCI
sparse track's EDA figures (`reports/figures/eda_*`, `forecast_fan`, …) while
the headline figures live in `reports_m5_full/figures/`. The web only uses the
list for the raw-artifacts fallback gallery (`ProjectDetail.tsx:169,274-285`),
so the page's "figures" section shows the non-headline track. Low severity;
either union the track dirs for 02 or accept and caption it.

**NEW-7 · `gen_sitemap.py` has no `--check`.** The other three generators are
freshness-gated; sitemap/robots/index.html rewrites are not. `sitemap.xml`
lastmod is uniformly 2026-11-02, predating the 11-03 waves (routes unchanged,
so cosmetic today). Add a `--check` when the identity decision lands, since
regenerating with the flipped default will rewrite four files at once.

### 2.4 What the rounds got right (verified, not assumed)

- **M5 full-panel migration is exemplary.** `reports_m5_full/metrics.json`
  reconciles to the cent with every quoted surface: convex_ensemble 0.6160835
  → "0.6161" (story.yaml:316, README.md:41,61, docs/projects/02 line 47);
  lgbm_pool_store 0.6216694 → "0.6217"; lgbm global 0.6601175 → "0.6601";
  seasonal_naive 0.8928984 → "0.8929"; per-level caption ranges (item level
  1.04–1.15 learned vs 1.39 floor) match `per_level_wrmsse` exactly;
  `runtime_seconds` 46508.7 ≈ README's "~12.9 h"; `FULL_CHECKSUMS`
  (m5_full.py:168-173) match committed `evaluation_metadata.json` checksums
  byte-for-byte; all four `m5_full_*` figure pairs exist; old subset figures are
  retained but shadowed with the precedence documented at `main.py:284-308`.
- **03 ensemble re-run reconciles.** README:306-311 and story.yaml:339-340
  tables (1,157 → 35 pages, 0.729 → 0.604 recall, 0.485 → 0.533 F1; 1,003 →
  45 / 0.562 / 0.365) match `nab_sweep.json` raw cells and `nab_tune.json`
  `default_budgeted@2%,24h` cells exactly; the short_version's "1,609 alerts,
  16 of 17" matches `isolation_forest+rolling_residual`; RELEASE-NOTES'
  "1,609 → 80, 0.157 → 0.315" matches the tuned artifact.
- **06 reconciles** (deep-check): summary gaps (4.2322/4.2993/18.3138/71.6395/
  316.9487/13.7535/13.6272 → the README table's 4.23/4.30/18.31/71.64/316.95/
  13.75/13.63), per-instance C103 11.6704 → "11.67 %".
- **Conclusions platform fully adopted.** All 10 stories carry the skeleton
  (Results summary / What the experiment taught / Exact numbers / Protocol /
  Limits — indentation differs per story but the renderer's `^##` multiline
  regex is indent-agnostic). Split logic (`StorySection.tsx:36-64,85-87,
  102-104,125-147`) is correct across its edge cases: no-skeleton → legacy
  collapsed layout (tested, `StorySection.test.tsx:301`), missing Limits →
  limits=null path (the common case — handled), takeaway split ordered before
  the technical split so cards never duplicate, `In plain terms` marker
  supported though no story uses it yet (forward-looking, not stale).
- **Generated surfaces all current:** `gen_static_registry --check`, storyShort
  map, route manifest (21 routes), short copy (40 surfaces), demo contract
  (both demos incl. the new `reports_m5_full` payload), story lint (10/0/0),
  `lint_ci` — all green on 2026-11-04.
- **No orphan artifacts found:** old 02 figure ids (wape_bars, sample_series,
  …) are referenced nowhere outside the retained `reports_m5/` track; both
  docs SVGs are referenced; zero TODO/FIXME; no unused component surfaced after
  the conclusions change (`MetricCallout` lives only in `delta.ts` and is
  consumed by `StoryMetricsTable`).
- **New drift-observatory workflow is well-built:** pinned actions, bounded
  runtime, macos-15 runner justified by arch-portable artifacts, exit-code 2
  (month not yet published) deliberately non-failing, issue-on-regression only
  (`drift-observatory.yml:42-82`).

---

## 3. Updatedness

- **Dependency pins:** unchanged since pass 1; drift vs PyPI re-verified
  2026-11-04 (table in §1 CQ P2-4). Policy is deliberate ("bump deliberately,
  not casually", `Dockerfile:17-18`), but the fastapi/starlette pair is now 19
  minors / 3 minors behind respectively, and it is the public attack surface —
  the pre-cutover bump wave from pass 1 is now more urgent, not less.
- **pip-audit:** still unverifiable locally (host `ensurepip` SIGABRT under
  uvx, same as pass 1 — an environment defect, not a repo defect). CI gate at
  `ci.yml:129-135` is authoritative; its latest status could not be checked
  from this environment.
- **Dates:** sitemap lastmod 2026-11-02 (one day behind the content waves;
  cosmetic — routes unchanged). README/docs carry dated claims current through
  the waves (e.g. 09's 2026-10-30 held-out expansion). `RELEASE-NOTES` result
  section dated 2026-10-29 but missing the 11-02/03 changes (NEW-3).
- **evaluation_metadata:** 02 full-panel runtime matches README; 03/06/09
  artifacts carry per-task/per-candidate timings consistent with their README
  claims (03 alert-budget numbers, 06 per-solver means, 09 per-task durations
  11–31 s vs the 60 s budget).

---

## 4. Gate results (all re-run 2026-11-04, CI-shaped)

| Gate | Result |
|---|---|
| libs + showcase-api (`pytest -n 2 --cov=libs --cov-fail-under=80`) | ✅ pass, 96.66 % |
| 01-rag-agent | ✅ 119 passed (83 % cov) |
| 02-demand-forecasting (unit+models, one run) | ✅ 196 passed (86 % cov) |
| 03-anomaly-detection | ✅ 94 passed (95 % cov) |
| 04-nlp-classification | ✅ 78 passed (65 % cov) |
| 05-ml-pipeline-churn | ✅ 61 passed (93 % cov) |
| 06-routing-optimization | ✅ 170 passed (90 % cov) |
| 07-open-data-mobility | ✅ 60 passed (74 % cov) |
| 08-inference-serving | ✅ 15 passed (64 % cov) |
| 09-agentic-workflows | ✅ 80 passed (88 % cov) |
| 10-uplift-experimentation | ✅ 60 passed (67 % cov) |
| ruff check + ruff format | ✅ 406 files |
| mypy libs projects apps | ✅ no issues in 164 files |
| mkdocs build --strict | ✅ clean |
| demo contract + static registry | ✅ (both demos; new M5 full payload wired) |
| short copy / route manifest / story lint / lint_ci | ✅ 40 surfaces · 21 routes · 10 stories · 20 targets |
| web `npm test` | ✅ 350/350 (38 files) |
| web `npm run build` + bundle budget | ✅ built; index chunk 70.6 KB gzip vs 250 KB gate |
| eslint (non-blocking in CI) | ✅ 0 problems locally — ready to become blocking |
| axe (non-blocking in CI) | ⚠️ 7 moderate / 0 serious across 6 routes (region ×6 routes, landmark-unique on 05) |
| `uv lock --check` | ✅ 333 packages, no changes |
| pip-audit | ⚠️ unverifiable locally (host ensurepip crash); CI gate authoritative |

Test counts moved vs pass 1 only upward (933 project tests total across the ten
cells). No flakes observed at the supported `-n 2`.

**Method note:** the axe run required booting the API and a vite dev server;
`scripts/axe_check.mjs` regenerates `reports/axe.json` in place, so that file
now holds the 2026-11-04 snapshot (pass-1's snapshot was identical for `/` —
33 passes / 1 violation — but per-route counts could not be diffed after the
fact). The vite dev server was stopped afterwards; the API on :8000 was
already running before this audit and was left untouched.

---

## 5. Dimension scores, justified

### Code quality — 8.5/10 (was 9)

Everything that held the score at 9 still holds: zero-type-error mypy over 164
files, ruff-clean 406 files, 933 behavior-shaped project tests green at the
supported parallelism, libs at 96.66 % against the 80 % gate, strict-typed
shared libs, sha-pinned loaders with actionable errors (the new `m5_full.py`
loader at `m5_full.py:212-279` is the best example in the repo: checksum pins,
schema assertions, contiguity guards, and generic shape validation that the toy
fixtures genuinely exercise). The -0.5 is NEW-1: a shipped logic bug in
`lib/delta.ts` (false baseline classification + cross-metric delta fallback)
that renders arithmetically valid but semantically false numbers on a public
page, with a unit test asserting the wrong behavior. It is two lines to fix;
until it is, "code quality" in the user-facing sense is not 9. The unchanged
CQ P2-1/P2-2/P2-4 items are the other small drags.

### Documentation — 8/10 (unchanged)

Three of four pass-1 P2s fixed (playbook, compose comment, docx archive), and
the two result waves were propagated with unusual discipline — README, docs
pages, story captions, and RELEASE-NOTES entries all reconcile to committed
artifacts to the cent (verified numerically for 02/03/06, gated mechanically
for the other 40 surfaces). Two things hold it at 8: the dual identity (dead
domain still every build's default; the single highest-leverage fix remains
undone a day after being named P1) and the new staleness class — a changelog
that omits the biggest change it exists to record (NEW-3).

### Infrastructure — 8/10 (unchanged)

The drift-observatory workflow is a real addition (scheduled, bounded,
issue-on-regression, honest exit-2 handling), eslint is now violation-free, and
the nightly/CI matrix reproduced green locally in full. But the three
non-blocking gates are still non-blocking with an axe snapshot that drifted
upward (7 moderate, one new class of violation), there is still nothing that
notices a dead VPS or expired certificate from outside, and the crown jewel —
the nightly byte-identity proof — now validates the legacy 02 track instead of
the canonical one (NEW-2). Gains and losses net to zero.

### Productization — 7/10 (unchanged)

The good: demo contract + static registry green against the migrated payload,
the clean-clone serving story still verified end-to-end by gates plus the live
API boot (`/health` ready, 02/05/06 serving smoke in CI), the artifacts tree
explained, RAG chat still fails closed. The bad: the launch identity is still
unreachable, the API contract is still unversioned, the release ritual is still
half-built, payload regeneration is still unscheduled for both the migrated
headline and 05 — and NEW-1 puts misleading deltas on the public project pages
themselves. Real gains canceled by standing debt plus one new visible defect.

---

## 6. Consolidated fix list

### P0
*None.*

### P1
1. **Fix the delta-table baseline bug** (`apps/showcase-web/src/lib/delta.ts:21,86-89`): no cross-metric deltas (null when the baseline lacks the candidate's metric), tighten baseline detection (word boundaries or explicit story-level declaration), and correct `delta.test.ts:9-13` (`random_forest` must not be a baseline) with a cross-metric regression case. *(NEW-1)*
2. **Re-aim the nightly determinism job at the canonical 02 track** (`nightly.yml:45-62`): `evaluate-m5-full` + `demo-payload-m5-full` run-twice `cmp` against `reports_m5_full/` (monthly cadence if 12.9 h is too heavy for nightly), plus 05's payload `cmp` as pass 1 recommended — or document the legacy-subset run as a deliberate cheap proxy. *(NEW-2 / PROD P2-3)*
3. **Launch identity** — unchanged from pass 1: publish DNS for `alejandromerida.dev` or flip the defaults (`config.ts:11`, `gen_sitemap.py:20`, `index.html`, `robots.txt`, `sitemap.xml`, plus the brand string `ProjectDetail.tsx:75` and mkdocs SEO URLs `mkdocs.yml:3,42-43` in the same motion), then regenerate. *(DOC P1-1 / PROD P1-1 / DOC P2-2)*
4. **Version the API contract** (OpenAPI/JSON-Schema golden in `apps/showcase-api/tests/`). *(PROD P1-2)*
5. **External probe**: scheduled `health`/`ready` + TLS-expiry check filing an issue. *(INFRA P1-1)*

### P2
6. Add the copy-guard hardcoded-origin assertion (pass-1 residual of DOC P1-2). *(NEW-5)*
7. RELEASE-NOTES: add the 02 full-panel entry + list the 2026-11-03 assessment in Audits. *(NEW-3)*
8. Flip eslint to blocking now that it is clean; fix the six `region` violations; date the axe-blocking wave; fix `landmark-unique` on 05's detail page. *(INFRA P2-1 / NEW-4)*
9. Fastapi/starlette bump wave before any DNS cutover; verify the latest CI pip-audit step. *(CQ P2-4)*
10. `make release` checklist target completing the release ritual. *(PROD P2-2)*
11. Note in DEPLOY.md's hybrid-split paragraph the three in-process guards needing a shared store. *(INFRA P2-3)*
12. `/projects/{pid}/figures` list should union 02's track dirs (or caption the gallery as the UCI track). *(NEW-6)*
13. `gen_sitemap.py --check` (with the identity flip). *(NEW-7)*
14. `pyproject.toml` pytest-ini comment naming `-n 2` as the validated parallelism; replace 08's scaffold test. *(CQ P2-1 / CQ P2-2)*
15. Optional, deliberate: adopt the `**In plain terms:**` marker in stories (code already prefers it) — currently 0/10 stories use it; harmless either way.

---

## Appendix A — verification log (commands run, 2026-11-04)

- DNS: `dig @1.1.1.1/@8.8.8.8 alejandromerida.dev A/AAAA/CNAME` → NS only, zero address records.
- `uv run pytest libs apps/showcase-api -q -n 2 --cov=libs --cov-fail-under=80` → pass, 96.66 %.
- Per-project cells `pytest -o addopts="--import-mode=importlib -q -n 2 --timeout=900" --cov=src` → all green: 119 / 196 / 94 / 78 / 61 / 170 / 60 / 15 / 80 / 60.
- `uv run ruff check .` + `ruff format --check .` → clean, 406 files.
- `uv run mypy libs projects apps` → Success, 164 files.
- `uv run mkdocs build --strict` → clean.
- `check_demo_contract.py`, `check_short_copy.py --check`, `gen_route_manifest.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `lint_story_language.py`, `lint_ci.py` → all green.
- Web: `npm test` → 350/350; `npm run build` → OK; index chunk 70.6 KB gzip vs 250 KB CI gate; `npx eslint .` → 0 problems.
- Axe live: API on :8000 + `npm run dev` on 4321, `AXE_BASE_URL=http://127.0.0.1:4321 node scripts/axe_check.mjs` → 6 routes, 7 moderate violations (0 serious/critical), `reports/axe.json` regenerated in place (see Method note, §4).
- Metrics reconciliation (python one-offs against committed JSON): 02 full-panel headline/per-level/runtime/checksums; 03 sweep + tune cells vs README/story tables and RELEASE-NOTES; 06 summary + per-instance vs README; 01 delta-table simulation per delta.ts logic.
- Baseline-regex sweep over every `projects/*/reports*/metrics.json` run name → only 01's `retrieval_random_chunks_*` false-positive.
- Skeleton sweep: `## Results summary/What the experiment taught/Exact numbers/Protocol/Limits` present in 10/10 stories (indentation differs; renderer regex indent-agnostic).
- Orphan sweep: old 02 figure ids unreferenced outside retained track; docs SVGs referenced; TODO/FIXME zero; vulture unavailable in env (replaced by ruff F-codes + targeted greps).
- `uv lock --check` → 333 packages, no changes. PyPI version probes (fastapi/starlette/pydantic/pydantic-ai/transformers/torch/polars) via pypi.org JSON.
- pip-audit: `uvx pip-audit` fails with host ensurepip SIGABRT (environment defect, same as pass 1).
