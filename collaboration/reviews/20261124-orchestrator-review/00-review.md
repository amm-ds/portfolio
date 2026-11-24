# Orchestrator review: production readiness, cleanup, content, apps/demos, RAG 01

Date: 2026-11-24
Reviewer: Claude Code (read-only review; no implementation files edited, no git
mutations, no hosted LLM or paid API calls)
Repo state: `main` @ `c09d9166`; only untracked path is
`collaboration/designs/20261124-wave6-experiments-apps-and-demos/`.
Audience: the orchestrator agent assigning work to Kimi Code.

Legend: **[V]** verified in this session (command run or file read, cited
file:line); **[I]** inference (reasoned from evidence, not proven).
Severity: **blocker** (must fix before the next public release),
**major** (fix in this wave), **minor** (fix when touching the file).

---

## 0. Executive summary

1. **Blocker, truth in copy (RAG 01).** Six public surfaces say the *owner*
   hand-labelled a blind 30-claim sample (30/30). The committed artifact says
   `"validated_by": "claude-role-audit (pending human owner hand-label
   confirmation)"`. The owner has not labelled it.
2. **Blocker, truth in copy (RAG 01).** The public faithfulness CI
   `[0.7983, 0.9155]` does not match the committed final metrics
   (`[0.8092, 0.9304]`). No committed final artifact contains the public pair.
3. **Major, RAG 01 visuals.** Every RAG figure (JSON and PNG) still shows the
   65-question pre-S3 runs. The Results section pairs final-pass text
   (F1 0.9091, 104/120 correct) with a 65-question taxonomy chart. The
   README hero PNG says recall@5 0.831. The production retriever now reaches
   0.9457.
4. **Major, project 02 copy.** The story says the erratic-routing arm's
   full-panel performance "remains unproven". The committed metrics show that
   arm was scored on the full-panel test window (0.6235, delta +0.0025, about
   3.9x the noise band, not "twice"). The 0.6211 headline is still correct.
5. **Traffic lights.** There are three implementations, not two. The Wave 6
   handoff misses the showcase-web one (`Terminal.tsx` + `shell.css`), which
   is the one in the top-left of the Home hero.
6. **Demo cards oversize.** `.app-main--fluid` has no width cap. `.demo-grid`
   is a fixed 2-column `1fr` grid. Each demo card is about 930px wide at
   1920px and about 1250px wide at 2560px. Unit tests lock the current CSS
   rule text by regex, so any fix must update
   `ProjectsIndex.test.tsx:315-325,394-409`.
7. **Gates (run today, local, offline).** ruff, ruff format, mypy (247
   files), RAG pytest (184 passed, 1 skipped), showcase-api pytest (102
   passed), and all 8 repo check scripts are green. The showcase-web vitest
   run **could not start** because of a local `@rollup/rollup-darwin-x64`
   optional-dependency/arch mismatch. This is an environment problem, not a
   code problem. The last recorded web pass is Wave 4.

---

## 1. Production readiness

### 1.1 Gates run in this session [V]

| gate | command (repo root unless noted) | result |
|---|---|---|
| lint | `uv run --offline ruff check .` | `All checks passed!` |
| format | `uv run --offline ruff format --check .` | `876 files already formatted` |
| types | `uv run --offline mypy libs projects apps` | `Success: no issues found in 247 source files` (5.4 s) |
| RAG tests | `cd projects/01-rag-agent && HF_HUB_OFFLINE=1 uv run pytest -o addopts=""` | `184 passed, 1 skipped, 2 warnings in 2.10s` |
| API tests | `uv run pytest apps/showcase-api -o addopts=""` | `102 passed in 2.89s` |
| docs | `scripts/check_docs.py` | `check-docs: OK` |
| short copy | `scripts/check_short_copy.py --check` | OK (39 surfaces, 13 stories) |
| demo contract | `scripts/check_demo_contract.py` | `demo-contract: OK` |
| story lint | `scripts/lint_story_language.py` | 0 errors, **1 warning**: 01 evaluation section 660 words (soft budget 550) |
| registries | `gen_static_registry.py / gen_story_short.py / gen_route_manifest.py --check` | all current (27 routes) |
| headline guard | `scripts/check_headline_numbers.py` | `11 claims checked, 0 finding(s)`, but 01 and 04 are **skipped** (see 3.1) |
| web tests | `cd apps/showcase-web && npx --no-install vitest run` | **did not start**: `Cannot find module @rollup/rollup-darwin-x64` |

Not run: `mkdocs build --strict` (it writes `site/`), the agent-chat and
document-intelligence suites, and `npm run lint/build`. Last recorded results:
`collaboration/reviews/20261124-wave4-apps/00-closeout.md:88-93` (agent-chat
coverage 90.19%, document-intelligence 85.00%, showcase-web
test/lint/build pass after `npm ci`) and
`collaboration/reviews/20261124-wave5-backend-and-hygiene/00-closeout.md:99-109`.

**Finding P1 (minor, environment) [V+I].** `node -v` = v26.7.0 while
`uname -m` = arm64, and rollup asks for the **x64** native module. So node is
running as an x64 binary under Rosetta, or `node_modules` was installed by a
different-arch node. Wave 4 hit the same class of error with the arm64 module
(`20261124-wave4-apps/00-closeout.md:82-85`). A likely contributor [I] is
`docker-compose.yml:22-28`: the `web-dev` service bind-mounts
`./apps/showcase-web` and runs `npm ci` inside `node:22-alpine`. That
overwrites the host `node_modules` with linux-musl binaries. Fix: add an
anonymous volume `- /web/node_modules` under `web-dev.volumes`, and use one
arm64 node on the host.

### 1.2 Deploy, Dockerfile, compose [V]

- `Dockerfile:19,31,44`: base images are pinned by digest. It is multi-stage,
  installs only the `showcase-api` subtree (`:74`), runs as a non-root user
  (`:79-80`), has a `/ready` healthcheck (`:85-86`), and sets forwarded-IP
  trust to loopback by default (`:93`). Good.
- `deploy/docker-compose.prod.yml`: required secrets use `:?` guards
  (`IP_HASH_SALT`), there is a read-only rootfs, `cap_drop: ALL`,
  `no-new-privileges`, the API port is unpublished, and Caddy terminates TLS.
  Good.
- **P2 (minor).** The root `docker-compose.yml:17` healthcheck probes
  `/health` while the image healthcheck (`Dockerfile:86`) probes `/ready`.
  Align them on `/ready`.
- **P3 (minor).** `docker-compose.yml:22-28`: see P1 (host `node_modules`
  clobbering).
- `.dockerignore` excludes `artifacts`, `site`, `node_modules`, `docs`,
  `**/tests` and `data`. Good.

### 1.3 Secrets and hard-coded hosts [V]

- A regex scan for `sk-…`, `AKIA…`, `ghp_…`, `hf_…`, `xox[bp]-`, private-key
  headers and inline `api_key="…"` over all tracked files finds no real
  secrets. The only hit is `apps/document-intelligence/tests/test_gateway_identity.py:28`
  (`"offline-test-key"`, a test fixture).
- Tracked env templates: `.env.example`, `apps/agent-chat/.env.example` and
  `apps/document-intelligence/.env.example`. All key values are placeholders
  (`your/replace/lm-studio`) or empty. `CONTACT_PHONE` examples are
  `+34 600 000 000` / `+34 000 000 000` (dummy).
- No hard-coded public IP URLs, apart from loopback.
- **P4 (major, privacy/hygiene).** Absolute local home paths are committed in
  a public repo:
  - `projects/01-rag-agent/reports/final_v3_file_access.json` has **3,365**
    occurrences of `/Users/<owner>/…` (file size 624 KB).
  - `projects/02-demand-forecasting/reports_m5_full/{report.html:38,evaluation_metadata.json,demo_payload.json,catalog_meta.json}`
    and `reports_m5/{report.html,evaluation_metadata.json}` have 1 each.
  - Fix [I]: make the writers emit repo-relative paths, then regenerate the
    artifacts (or post-process with a deterministic path rewrite). Owner
    approval is needed because these are evidence artifacts.
- 12 tracked files under `collaboration/` also contain the absolute path
  (minor; internal notes).

### 1.4 Structural size (thermo-nuclear bar, minor) [V]

These files are over 1,000 lines: `projects/01-rag-agent/src/rag_agent/evaluate.py`
(2,435), `apps/showcase-web/src/lib/plotlyToECharts.ts` (2,386),
`projects/02-demand-forecasting/src/demand_forecasting/m5_track.py` (2,342),
`m5_full.py` (2,132), `apps/showcase-web/src/styles/pages.css` (1,680),
`apps/showcase-api/src/showcase_api/main.py` (1,224), and three project
`evaluate.py` files of about 1,000 to 1,500 lines. No action this wave. Do not
let a change grow them further.

---

## 2. Code cleanup

### 2.1 Root `node_modules`, `site`, `reports` [V]

| dir | tracked? | ignored by | size | verdict |
|---|---|---|---|---|
| `node_modules/` | no (0 files) | `.gitignore:64` `node_modules/` | 3.5 MB (`.vite`, `.vitest-cache` only) | stray local cache from a root-level vite/vitest run. Safe to delete locally; no repo change |
| `site/` | no | `.gitignore:73` `/site/` | 16 MB | mkdocs build output; fine |
| `reports/` | **yes**, 1 file: `reports/axe.json` | n/a | 24 KB | written by `scripts/axe_check.mjs:6` and uploaded by `.github/workflows/ci.yml:345`. Committing a CI artifact means it goes stale (**minor**): either stop tracking it and keep it as a CI upload, or document that it is the release snapshot |
| `artifacts/` | no | `.gitignore:41` `artifacts/` | **12 GB** local | local scratch (zips, Playwright runs). Not in git or the image; disk hygiene only |
| `apps/artifacts/` | no | `artifacts/` pattern | empty `spot-check/` | stray; delete locally |

### 2.2 TODO/FIXME [V]

`git grep -E "TODO|FIXME|XXX|HACK"` over `*.py, *.ts, *.tsx, *.css, *.mjs`:
**0 hits**.

### 2.3 Dead or duplicate media [V]

`apps/showcase-web/public/apps/` (md5 + reference grep over `apps/showcase-web/src`,
`apps/*/web/scripts`, `docs`):

| file | md5 duplicate of | referenced by | verdict |
|---|---|---|---|
| `agent-chat-ui.png` | `agent-chat-ui-v2.png` | nothing in the web app (docs use `docs/assets/apps/agent-chat-ui.png`, a different file) | dead |
| `agent-chat-ui-v2.png` | `agent-chat-ui.png` | nothing | dead |
| `agent-chat-approval.png` | `agent-chat-approval-v2.png` | nothing | dead |
| `agent-chat-approval-v2.png` | `agent-chat-approval.png` | nothing | dead |
| `agent-chat-memory.png` | `agent-chat-memory-v2.png` | nothing | dead |
| `agent-chat-memory-v2.png` | `agent-chat-memory.png` | nothing | dead |
| `agent-chat-{ui,approval,memory}-v3.png` | (unique) | `AgentChatArticle.tsx:261,266,280,351`, `lib/apps.ts:34`, `record-demo.mjs:127,132,142` | live |
| `agent-chat-demo.{mp4,webm,vtt}` | (unique) | `AgentChatArticle.tsx:280-282` | live |
| `document-intelligence-{summary,qa}.png` | identical to `docs/assets/apps/` copies | `DocumentIntelligenceArticle.tsx:282,287`, `lib/apps.ts:50` | live |

That is 6 dead PNGs, about 0.9 MB.

`docs/assets/` PNGs with **no reference** in docs, mkdocs, READMEs, stories
or the web src [V]:
`projects/01-rag-agent/failure_taxonomy.png`,
`projects/02-demand-forecasting/{forecast_vs_actual,metrics_bars}.png`
(generated from the **old UCI** `reports_uci/figures`, see
`scripts/export_readme_figures.py:37-40`),
`projects/04-nlp-classification/epochs_probe.png`,
`projects/05-ml-pipeline-churn/cost_surface.png`,
`projects/11-data-engineering/normalized_heatmap.png`.
These are still listed in `scripts/export_readme_figures.py:35-52`
(`DOCS_FIGURES`), so a rerun would regenerate the orphans. Prune them from
`DOCS_FIGURES` at the same time.

Intentional byte-identical copies (fine): `docs/assets/readme/anomaly-timelines.png`
= `docs/assets/projects/03-anomaly-detection/nab_timelines.png`;
`docs/assets/readme/mobility-demand-map.png` = `.../07-open-data-mobility/zone_demand_map.png`.

### 2.4 Scripts [V]

The following have no references outside `collaboration/` and themselves:
`scripts/build_social_card.py`, `scripts/export_readme_figures.py` (a manual
generator named in AGENTS.md as "README figures", so keep it), and four
`scripts/tests/test_*.py` (collected by pytest; fine). Nothing is clearly
dead. Do not delete without owner approval.

### 2.5 Committed review screenshots [V]

`collaboration/` tracks 37 media files, about 7.8 MB in total (for example
`collaboration/reviews/20261119-ui-report/screenshots/*.png`, some byte-identical
pairs). Minor. Owner decides whether review media stays in a public repo.

---

## 3. Content quality

### 3.1 Truth in copy: traceability table

| # | claim (surface:line) | committed source | status |
|---|---|---|---|
| C1 | "the owner hand-labelled a 30-claim blind sample … 30/30" (`projects/01-rag-agent/README.md:72-74`, `story.yaml:222-225`, `story.yaml:458`, `docs/projects/01-rag-agent.md:179`); "owner-validated at **30/30** blind agreement" (`apps/showcase-web/src/lib/cardCopy.ts:45`); "Judge calibrated 30/30 blind" (`story.yaml:2` short_version, regenerated into `storyShort.ts`, `README.md:9`, `docs/projects/01-rag-agent.md:5`) | `reports/judge_calibration_v2/owner_sample_validated.json`: `"validated_by": "claude-role-audit (pending human owner hand-label confirmation)"`; the review that "validated" it was a Claude audit (`collaboration/reviews/20261123-rag-sota-retrieval-and-pipeline/01-review-response.md`, disposition table); the Kimi close-out says "agreement against the owner's hand labels is NOT computed" (`.../00-closeout.md`, Phase A) | **blocker**: false attribution [V] |
| C2 | faithfulness 0.8717 **[0.7983, 0.9155]** (`projects/01-rag-agent/README.md:92`, `story.yaml:372`, `docs/projects/01-rag-agent.md:84`; also the Phase E close-out `:72`) | `reports/final_v3_e2e/metrics.json` → `detail.final_v3.faithfulness.ci95 = [0.8092, 0.9304]` | **blocker**: the CI in copy is untraceable [V]. [I] It probably comes from the pre-dedupe 240-row aggregates that the close-out says were regenerated (`20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md:59-65`) |
| C3 | correct_share CI [0.8167, 0.9083]; answer_relevance 0.8804; context_recall 0.9891 (Phase E close-out `:73-76`) | `metrics.json`: correct_share_ci95 `[0.8, 0.925]`, answer_relevance `null`, context_recall `1.0` | **major** if quoted publicly. Grep of the public surfaces found none of these three [V], so the drift is internal for now |
| C4 | F1 0.9091 / P 0.9524 / R 0.8696 / accuracy 0.8667, 1/120 unsupported, slices 60/68, 20/24, 24/28 | `reports/final_v3_e2e/f1_summary.json`, `metrics.json` | traceable [V] |
| C5 | S3 recall@5 0.9457 vs 0.9239; multi-hop 0.8333 vs 0.7917 (`story.yaml:133-134,449`, `docs/projects/01-rag-agent.md:176-177`) | `reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json` (0.94565), `reports/retrieval_baseline/final_v3.json` (0.92391) | traceable [V]; see 5.2 for contamination |
| C6 | 01 headline guard | `scripts/check_headline_numbers.py:32` `KNOWN_DRIFT = {"uncovered:01-rag-agent", "uncovered:04-nlp-classification"}`; docstring `:15-17` says 01 has "no single committed scalar headline" | **major**: no longer true. `f1_summary.json:f1` is a clean scalar, so 01 can be covered [V] |
| C7 | 01 `reports/metrics.json` | `_meta.created_at 2026-11-16`; `rag_agent.faithfulness 0.6209` (wave-14) | **major**: conflicts with `repo-conventions.md` "Headline `reports/metrics.json` belongs in git". The 01 headline now lives in `final_v3_e2e/`. A prior review chose to leave it untouched (`20261123-rag-sota-retrieval-and-pipeline/01-review-response.md`). Owner decision D5 |
| C8 | 02 headline 0.6211 (`story.yaml:21,227,236,255,271`, `README.md:95,104,109`, `cardCopy.ts:47`, `storyShort.ts:12`, `docs/projects/02-demand-forecasting.md:7,47`) | `reports_m5_full/metrics.json:245` `test.official_wrmsse.convex_ensemble = 0.62105` | traceable [V]. **0.6235 is the rejected erratic arm** (`:247`) and appears in no copy surface. Correct as is |
| C9 | 02 erratic arm "evidence comes only from that capped window. Its full-panel performance remains unproven" (`story.yaml:253-255`) and "scored twice the noise band worse" (`story.yaml:250`, `:289-290`) | `reports_m5_full/metrics.json:244-248` (full-panel test score 0.62354), `:267-279` (delta_point 0.002488, noise_tol 0.000644, ratio about 3.9x), `:289-293` | **major**: the copy contradicts the committed artifact [V]. Also [I]: the adoption gate used the **test** window. That is a second use of the "scored-once" window (`story.yaml:284-285`), so the copy should say so. The champion is unchanged, so the headline survives |
| C10 | 02 zero-day accuracy "57.3%" (`story.yaml:287`, `:338`, `:385`) vs "57.2%" (`story.yaml:109,174,240`, `README.md:125,134`) | `reports_m5_full/metrics.json` `test.convex_ensemble.zero_day_accuracy = 0.5724` | **minor**: 57.3% is a mis-rounding; use 57.2% [V] |

### 3.2 Stale RAG captions vs promoted pipeline [V]

- `story.yaml:522` (`fusion_arm_comparison`): "so fusion is not promoted over
  the dense+rerank champion". S3 **is** a BM25+dense RRF hybrid and was
  promoted (`story.yaml:129-133`). This contradicts the case study's own text.
  **Major.**
- `story.yaml:515,516,517,519,520,521`: all captions describe 65-question
  pre-S3 runs (recall@5 0.831, 46/17/2/0 taxonomy, p95 108.836 s). The Results
  section (`story.yaml:339` `figures: [retrieval_hpo_frontier, failure_taxonomy]`)
  shows them beside the final 120-question numbers. **Major** (see 5.4).
- `docs/projects/01-rag-agent.md:99` embeds `chunk_size_sweep.png`
  ("200-token chunks hold full recall@5 …"). Production now uses
  structure-mode chunks (S3). **Minor**: label it as history or replace it.
- Story-lint warning: the 01 evaluation section is 660 words against a 550
  budget (`scripts/lint_story_language.py` output). **Minor.**

### 3.3 Em-dash overuse [V]

Prose em-dash clause joins (`" — "` outside `|` table rows) per file.
`repo-conventions.md` says "Avoid em-dash clause joining by default":

| file | count |
|---|---|
| `projects/06-routing-optimization/README.md` | 45 |
| `projects/04-nlp-classification/README.md` | 35 |
| `projects/02-demand-forecasting/README.md` | 35 |
| `projects/11-data-engineering/README.md` | 32 |
| `docs/projects/09-agentic-workflows.md` | 24 |
| `docs/projects/01-rag-agent.md` | 17 |
| `docs/apps/chatbot-agent.md` | 17 |
| `projects/10-uplift-experimentation/README.md` | 16 |
| `docs/projects/10-uplift-experimentation.md` | 15 (e.g. `:23,29,32`) |
| `docs/projects/08-inference-serving.md` | 13 |
| `projects/{01,12}-*/README.md` | 12 each |

**Minor**, mechanical but large. Do it per file, rewriting to periods or
commas, and never inside tables, ranges or YAML.

### 3.4 Placeholders and broken links [V]

- No `lorem|TBD|TODO|coming soon|[insert` hits in docs, stories, READMEs,
  web pages or cardCopy.
- `check_docs.py` OK. All 24 `mkdocs.yml` nav entries exist on disk.
  29 docs pages (project and data-registry pages, `apps/agent-chat-ui.md`)
  are not in the nav but are linked from index pages. Fine under
  `--strict` per the earlier closeouts. `docs/apps/agent-chat-ui.md` is
  reachable only by link (minor).

---

## 4. Apps and demos

### 4.1 macOS traffic-light dots: every file and selector [V]

| app | markup | styles |
|---|---|---|
| **showcase-web** (Home hero, top-left; Glossary) | `apps/showcase-web/src/components/Terminal.tsx:3` (doc comment "traffic-light dots"), `:8-12` (`<span className="terminal-dots" aria-hidden="true"><span/><span/><span/></span>`); used by `src/pages/Home.tsx:54,67` and `src/pages/Glossary.tsx:11` | `apps/showcase-web/src/styles/shell.css:178-182` `.terminal-dots`, `:184-189` `.terminal-dots span`, `:191-193` `:nth-child(1)` (`--danger`), `:195-197` `:nth-child(2)` (`--warning`), `:199-201` `:nth-child(3)` (`--ok`) |
| **agent-chat** | `apps/agent-chat/web/src/components/chat/ChatSurface.tsx:46-50` (inside `.chat-titlebar` `:45`) | `apps/agent-chat/web/src/styles.css:183-187` `.terminal-dots`, `:189-194` span, `:196-198` nth-child(1), `:200-202` nth-child(2) (hard-coded `#fbbf24`), `:204-206` nth-child(3) |
| **document-intelligence** | `apps/document-intelligence/web/src/App.tsx:25` (inside `.brand`, app header top-left) | `apps/document-intelligence/web/src/styles.css:118-121`, plus the mobile hide `:364` (`.terminal-dots { display: none; }`) |

Notes:
- No literal `#ff5f57/#febc2e/#28c840` anywhere. Colours come from tokens.
  No unit test references `.terminal-dots` (grep of `__tests__` and `*.test.tsx`
  shows none).
- **Handoff gap (major).**
  `collaboration/designs/20261124-wave6-experiments-apps-and-demos/03-implementation-handoff.md`
  Part B lists only agent-chat and document-intelligence. It omits
  showcase-web `Terminal.tsx`/`shell.css`, which is the most visible instance.
- After removal, check the titlebar spacing. `.terminal-titlebar`
  (`shell.css:167-176`) has `gap: 0.5rem` and the dots carried
  `margin-right: 0.5rem`. The title text will move left by about 50px. That
  is acceptable, but recheck at 375px.
- Captured media also shows the dots (viewed in this session): document-intelligence-summary.png
  (top-left), agent-chat-approval-v3.png (titlebar). So the media must be
  re-captured after the code change.

### 4.2 Media inventory and staleness [V]

`apps/showcase-web/public/apps/` (last commit date in brackets):
`agent-chat-*-v3.png`, `agent-chat-demo.{mp4,webm,vtt}`, `document-intelligence-{summary,qa}.png` [2026-11-08];
6 dead PNGs (2.3); `social-card.png` [2026-11-11]; logos (SVG).

`docs/assets/apps/`: `agent-chat-{ui,approval,memory}.png` [2026-11-05]. These
are **different bytes** from the web `-v3` set, so docs and web show
different captures. `document-intelligence-{summary,qa}.png` [2026-11-08] are
identical to the web copies.

What is stale and why:

| asset | why stale | severity |
|---|---|---|
| all agent-chat and document-intelligence screenshots and the demo video | show the traffic-light dots being removed; captured 2026-11-05/08, before the Wave 4 apps alignment (2026-11-24) | major |
| `docs/assets/apps/agent-chat-*.png` | an older capture than the web `-v3` set; docs and web disagree | minor |
| `docs/assets/projects/01-rag-agent/failure_taxonomy.png` [2026-10-19] | shows 44/2/18/1 for a "hosted 65-question run" (viewed). That does not even match the current JSON (46/2/17/0), and the final pass is 104/120 | major (and orphaned, see 2.3) |
| `docs/assets/projects/01-rag-agent/chunk_size_sweep.png` [2026-10-19] | pre-S3 size-mode chunks; embedded at `docs/projects/01-rag-agent.md:99` | major |
| `docs/assets/readme/rag-quality-cost-frontier.png` [2026-10-19] | README hero (`README.md:36`), rendered from `reports/figures/retrieval_hpo_frontier.json` [2026-10-19]: recall@5 0.831 vs the promoted 0.9457 | major |
| `projects/01-rag-agent/reports/figures/{failure_taxonomy,retrieval_funnel}.json` [2026-11-18] | 65-question data (`failure_taxonomy`: 46/2/17/0; `retrieval_funnel`: 54 hit / 11 miss), served live to the web via `/projects/01-rag-agent/figures/*` | major |
| `docs/assets/projects/02-demand-forecasting/*.png` | generated from `reports_uci` (old dataset), orphaned | minor (delete) |
| other projects' docs PNGs [2026-10-19 to 11-11] | reports for 03-13 last changed 2026-11-16 to 11-19; no evidence the figure JSON changed after the PNG export. [I] Spot-check by re-exporting and diffing | minor |

Re-capture constraints [V]:
- `apps/document-intelligence/web/scripts/capture-demo.mjs:8-25` uploads the
  committed fixture `public/fixtures/cv.pdf` to a local API
  (`127.0.0.1:8001`). It is local-only, so Kimi can do it.
- `apps/agent-chat/web/scripts/record-demo.mjs:10-20` records against a
  running backend (the existing capture shows `kimi-for-coding@kimi`, a hosted
  model). A local mock exists (`VITE_MOCK=1`,
  `apps/agent-chat/web/src/App.tsx:9-17`, `lib/chat/mock.ts`), but a
  mock-recorded video would change what the article claims to show. This is
  owner decision D3 (hosted re-record vs mock vs local Ollama).

### 4.3 Demos and cards layout [V]

Current rules:

| selector (file:line) | rule | effect at wide viewports |
|---|---|---|
| `.app-main--fluid` (`src/styles/tokens-base.css:240-248`) | `max-width: none; padding: 0.5rem 1.25rem 3.5rem` | content width = viewport − 40px. **No cap anywhere above the grids** |
| `.demo-grid` (`src/styles/cards-grids.css:4-10`) | `grid-template-columns: 1fr` | — |
| `@media (min-width: 720px) .demo-grid` (`cards-grids.css:13-17`) | `repeat(2, minmax(0, 1fr))`, gap `--gap-card` = 1.25rem (`tokens-base.css:19`) | each card = (viewport − 60px) / 2 |
| `.project-grid` (`cards-grids.css:215-227`) | same 1 → 2 columns at 720px | same oversizing for the 13 experiment cards |
| `.apps-grid` (`cards-grids.css:246-257`) | 1 → 2 columns at 960px | same |
| `.app-card__shot` (`cards-grids.css:301-309`) | `width: 100%; height: 180px; object-fit: cover` | at 1250px wide it is a 180px crop strip (about 7:1) of a 16:10 screenshot |
| `.wb-root` (`src/styles/demos.css:292-312`) | `grid-template-columns: minmax(0, 1fr) 340px`; `min-height: calc(100dvh - 58px - 1rem)` | the chart column is about 2,140px wide at 2560px |
| `.wb-canvas-slot .figure-card` (`demos.css:465-475`) | `min-height: 460px` | about 4.6:1 chart aspect at 2560px |
| `.wb-secondary` (`src/styles/demos-workbench.css:301-307`) | `repeat(3, minmax(0,1fr)); height: 280px` | three about 830 × 280 panels at 2560px |
| workbench breakpoints | `demos-workbench.css:505` `@media (max-width: 900px)`, `:623` `(min-width: 390px) and (max-width: 900px)` | nothing above 900px; no large-screen rules |

Computed demo-card width (content = vw − 40px, gap 20px, scrollbar ignored):

| viewport | current card width | proposal A (cap grid at 72rem) | proposal B (auto-fill, min 22rem, grid cap 100rem) |
|---|---|---|---|
| 375 | 335 (1 col) | 335 | 335 (1 track) |
| 768 | 354 (2 col) | 354 | 354 (2 tracks) |
| 1280 | 610 | 566 | 400 (3 tracks) |
| 1440 | 690 | 566 | 453 (3 tracks) |
| 1920 | **930** | 566 | 385 (4 tracks in the 1,600px cap; 2 filled) |
| 2560 | **1,250** | 566 | 385 (same) |

Proposal B leaves empty tracks while there are only 2 demos, so A suits the
current content better.

The values that cause oversizing at ≥1920 and ≥2560: `max-width: none`
(`tokens-base.css:241`) combined with the fixed `repeat(2, minmax(0, 1fr))`
(`cards-grids.css:15`, `:225`). The `1fr` tracks have no upper bound.

Proposed CSS (do not implement in review; for Kimi):

```css
/* Proposal A: smallest change. Keeps the 2-column contract the tests lock. */
.demo-grid,
.project-grid {
  max-width: 72rem;            /* 1152px; 2 cards top out at ~566px */
}

/* Proposal B: intrinsic grid, use if the demo count grows past 2. */
.demo-grid {
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
  max-width: 100rem;           /* 1600px */
}

/* Readable measure inside any card, whatever the track width */
.study-card__content { max-inline-size: 70ch; }

/* App screenshots: keep the capture's aspect instead of a fixed 180px strip */
.app-card__shot {
  height: auto;
  aspect-ratio: 16 / 10;
  max-height: 22rem;
}

/* Workbench: bound the dashboard on large monitors; container queries
   replace the viewport-only 900px breakpoint */
.wb-root {
  max-width: 112rem;           /* 1792px */
  margin-inline: auto;
  grid-template-columns: minmax(0, 1fr) clamp(300px, 22vw, 400px);
  container-type: inline-size;
}
.wb-canvas-slot .figure-card { min-height: clamp(400px, 48vh, 640px); }
.wb-secondary { height: clamp(240px, 24vh, 360px); }
@container (max-width: 900px) { /* move the demos-workbench.css:505 rules here */ }
```

Test impact [V]: `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx:315-325`
asserts `@media (min-width: 720px)` and the `repeat(2, minmax(0, 1fr))`
string, and forbids `repeat(3` in `.project-grid`. `:394-409` regex-matches
the `.demo-grid { … }` block (`grid-template-columns: 1fr;`) and the 720px
two-column block. `:1049` asserts `gap: var(--gap-card);`.
`AppShell.test.tsx:174-176` reads the `.app-main--fluid` rule.
`ChurnSandbox.test.tsx:551` and `ForecastWorkbench.test.tsx:419-422` query
`.wb-secondary`. Proposal A keeps every assertion passing (it only adds
`max-width`). Proposal B needs `ProjectsIndex.test.tsx:394-409` rewritten.
Prior owner decision (cards top out at 2 columns,
`ProjectsIndex.test.tsx:319-321`) means B on `.project-grid` needs owner
approval (D7).

Also [V]: the Wave 6 handoff names `.demo-shell`. No such selector exists in
`apps/showcase-web/src` (grep: 0 hits). Kimi should target
`.demo-grid`, `.project-grid`, `.apps-grid`, `.app-card__shot`, `.wb-root`
and `.wb-secondary`.

Verification at 375 / 768 / 1280 / 1440 / 1920 / 2560 should use Playwright
screenshots under `artifacts/` (gitignored), not committed.

### 4.4 Backend readiness [V]

| app | entry points | config | tests | notes |
|---|---|---|---|---|
| `apps/showcase-api` | `showcase_api.main:app` (`Dockerfile:93`) | env (see `deploy/docker-compose.prod.yml`), fail-closed kill switches | 1 file `tests/test_api.py` (1,994 lines), **102 passed today** | `main.py` is 1,224 lines (>1,000, minor) |
| `apps/agent-chat` | `agent-chat-ingest` (`pyproject.toml:31-32`); FastAPI under `src/agent_chat/api`; `infra/{Dockerfile,docker-compose.yml}` | `.env.example` placeholders | 17 test files, `--cov-fail-under=89.8` (`pyproject.toml:71`); Wave 4: 90.19% | local `agent_chat.db` is ignored (`apps/agent-chat/.gitignore:9`) |
| `apps/document-intelligence` | `document-intelligence-worker`, `document-intelligence-eval` (`pyproject.toml:30-32`); alembic migrations; `infra/` | `.env.example` placeholders | 14 test files, `--cov-fail-under=84.5` (`pyproject.toml:70`); Wave 4: 85.00% | coverage margin is only 0.5 pp over the floor (minor) |
| `apps/artifacts` | n/a | n/a | n/a | not an app: an empty, ignored stray dir (`apps/artifacts/spot-check/`). Root `artifacts/` (12 GB) is ignored scratch |

---

## 5. RAG experiments (projects/01-rag-agent)

### 5.1 What is final [V]

| result | n | source | trust level |
|---|---|---|---|
| final_v3 E2E: F1 0.9091, P 0.9524, R 0.8696, accuracy 0.8667 (Wilson [0.7944, 0.9162]); TP 80 / FP 4 / TN 24 / FN 12; taxonomy 104 correct / 10 empty-answer / 4 budget-terminated / 1 unsupported / 1 retrieval-miss | 120 | `reports/final_v3_e2e/{f1_summary,metrics}.json`, checkpoint `reports/runs/final_v3-432d6b705715/` (120 rows) | final, reproducible from committed rows; caveats in 5.2 |
| S3 retrieval on final_v3: recall@5 0.9457 (Wilson [0.879, 0.977]), MRR@5 0.8877, multi-hop 0.8333 | 92 answerable | `reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json` | final, **selection-biased** (5.2) |
| R0 retrieval on final_v3: recall@5 0.9239 | 92 | `reports/retrieval_baseline/final_v3.json` | final |
| dev_v1 E2E F1 1.0 | 20 | `reports/e2e_dev_v1/` | **not evidence**: the Revision 1 fixes were designed from these exact failing rows (`20261123-rag-phase-e-e2e-and-judge-fix/01-review-response.md`) |
| Experiment log | 336 rows (301 judge-calibration-v2, 18 sweep, 6 baseline, 6 e2e, 5 promote) | `reports/experiment_log.json` | complete record [V] |

Note [V]: `final_v3_e2e/metrics.json` `detail.final_v3.retrieval.recall@5 =
0.7583` uses n=120 with a different gold mapping, so it differs from the S3
report's 0.9457 on n=92. It is not quoted publicly, but a reader of the
metrics file will see two "recall@5" values for the same set. Add a one-line
note or rename the key (minor).

### 5.2 Contamination of final_v3 [V unless marked]

final_v3 was read at least **four** times. `reports/final_v3_file_access.json`
logs file access during drafting only.
1. R0 retrieval baseline, step 5 (`20261122-rag-execution-plan/00-closeout.md:94-108`).
2. S3 **promotion gate**: "S3 beat R0 on final_v3 with no slice regression →
   promotion applies" (`20261123-rag-sota-retrieval-and-pipeline/00-closeout.md`,
   Phase B). A final-set result decided a production change, so the 0.9457
   number is selection-biased. The bias is small, because S3 was chosen on
   dev_65/heldout_55 first and final_v3 only confirmed it [I].
3. `validate_heldout_set` on `golden_final_v3.json` with S3 (`…/01-review-response.md`, Phase C).
4. The Phase E E2E pass, after which `runner.py` merge-dedupe was fixed and
   the aggregates were regenerated without a model rerun
   (`20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md:59-65`). That fix is
   aggregation-only [V]. Wave 1C copy and any later pipeline edits were made
   after viewing final_v3 traces [I], so **final_v3 can no longer serve as a
   sealed set for any further change**.

Other validity issues:
- **Same model in three roles (major) [V].** Generator, verifier and judge are
  all `kimi-for-coding` (`final_v3_e2e/metrics.json` → `meter.phases.{agent,verify,judge}`,
  `ops.backend: env:kimi-for-coding`). Faithfulness 0.8717 and the
  unsupported-claim count are self-judged. Self-preference bias is not
  measured.
- **Judge calibration measures the wrong distribution (major) [V+I].** The 147
  calibration claims are 75 supported plus 72 *constructed one-detail
  mutations* (`…sota…/00-closeout.md`, Phase A). The judge's 147/147 and 30/30
  agreement is on synthetic, easy negatives. Agreement on the generator's
  real claims is unmeasured.
- **The copy says "sealed" and "once"** (`README.md:14,81`, `cardCopy.ts:45`).
  The E2E pass was single, which is true. But final_v3 retrieval was read
  three times and gated a promotion. Recommend adding one sentence of
  disclosure (owner decision D2).

### 5.3 Judge calibration status [V]

- `reports/judge_calibration_v2/owner_sample.json`: 30 items, seed 44, note
  "UNLABELLED owner sample: label each claim … by hand".
- `owner_sample_validated.json`: `agreement 1.0`, Wilson `[0.886487, 1.0]`,
  `passes_gate true`, **`validated_by: "claude-role-audit (pending human
  owner hand-label confirmation)"`**. Each item carries `kimi_label` next to
  `validated_label`, so there is no evidence the audit was blind to the judge
  labels [I].
- Owner hand-labelling: **not done**. Every public "owner" or "blind" claim (C1)
  is unsupported until it is.

### 5.4 Visualizations: what exists vs what is needed [V]

Existing (`projects/01-rag-agent/reports/figures/*.json`, served to the web,
PNG statics under `docs/assets/`): `eda_corpus_composition`,
`retrieval_funnel` (65 q), `chunk_size_sweep` (65 q), `model_comparison`
(65 q), `latency_histogram` (65 q hosted), `kimi_generation_comparison`
(65 q), `fusion_arm_comparison`, `retrieval_hpo_frontier` (65 q),
`failure_taxonomy` (65 q). **None reflects S3 or final_v3.** Generators exist
in `src/rag_agent/figures.py` (`taxonomy_figure(traces)` `:310`,
`retrieval_funnel_figure` `:246`, `latency_figure` `:351`, `frontier_figure`
`:367`, `fusion_arm_figure` `:406`), so most updates mean re-feeding committed
data, not new code.

Missing to "update the RAG project with the new results and visualizations":
1. `failure_taxonomy`, rebuilt from `reports/final_v3_e2e/question_traces_heldout.json`
   (104/10/4/1/1, n=120). Caption at `story.yaml:521`.
2. `retrieval_funnel` (or a replacement `retrieval_ladder`): R0/S1/S2/S3 ×
   dev_v1/dev_40/dev_65/heldout_55/final_v3 from `reports/retrieval_sweeps/*.json`
   and `retrieval_baseline/*.json`, with recall@5, all_articles@5 and Wilson
   whiskers. Caption at `story.yaml:515`.
3. A final-pass outcome figure: the confusion counts TP/FP/TN/FN plus slices
   single/multi/unanswerable (60/68, 20/24, 24/28).
4. A verify-loop funnel: drafted 166 → mechanical fail 16 → judged 150 →
   supported 148 → accepted 159 (148 original + 11 repaired) → dropped 7
   (`metrics.json` `detail.final_v3.verify`).
5. `latency_histogram` for final_v3 (p50 16.47 s, p95 40.47 s are in
   `metrics.json ops`; per-row latencies are in the checkpoint rows) [I].
6. README hero: retarget `scripts/export_readme_figures.py:29`
   (`rag-quality-cost-frontier.png` ← `retrieval_hpo_frontier`) to the new
   ladder or outcome figure, re-export, and update `README.md:36` alt text.
7. Docs: update `docs/projects/01-rag-agent.md:99` and `DOCS_FIGURES["01-rag-agent"]`
   (`export_readme_figures.py:36`).
8. Captions `story.yaml:515-522`: rewrite to the new data, and fix the
   `fusion_arm_comparison` "not promoted" contradiction (3.2).
9. Reclassify the 65-question figures (`chunk_size_sweep`, `model_comparison`,
   `kimi_generation_comparison`, `retrieval_hpo_frontier`) as development
   history in DESIGN.md, or caption them clearly as tuning-set history
   (conventions: "Present last results only").

### 5.5 Validation round: what it should do (zero hosted calls except V4, which is owner-gated)

- **V1 (offline, $0).** Re-aggregate final_v3 from the committed checkpoint
  (`scripts/run_e2e_eval.py --summarize`, per the Phase E close-out) and
  assert byte-equality of F1/P/R/taxonomy. Recompute the faithfulness and
  correct_share CIs with a fixed seed. Resolve C2/C3 against that output.
- **V2 (owner, $0).** The owner hand-labels `owner_sample.json` with the Kimi
  labels hidden. Kimi computes agreement and Cohen's kappa, and writes
  `owner_sample_validated.json` with `validated_by: owner`. Only then may copy
  say "owner" or "blind".
- **V3 (owner, $0).** Real-distribution calibration: sample about 40 claims
  from the final_v3 accepted answers (stratified by slice), have the owner
  label them, and compare with the judge verdicts. This measures self-judge
  error on real outputs.
- **V4 (optional, owner-gated).** A cross-judge rerun of the final_v3 traces
  with a different model family (local Ollama qwen3 at $0, or a hosted
  non-Kimi judge under budget). Report agreement and the faithfulness shift.
- **V5 (process).** Declare final_v3 *consumed*. Any future retrieval or agent
  change is measured on a new sealed set (final_v4), drafted under the same
  file-access logging.
- **V6 (repro).** `HF_HUB_OFFLINE=1` retrieval re-measurement of S3 on
  final_v3 from the committed index config (local, $0) to confirm 0.9457 is
  reproducible.

### 5.6 Performance benchmark for the other projects

Coverage today [V]: `scripts/check_headline_numbers.py` derives 11 headline
claims from committed metrics for 02, 03 and 05-13 (`:47-133`); 01 and 04 are
skipped (`:32`). Report freshness: 03-06, 10, 12 and 13 reports were last
committed 2026-11-19; 07 on 2026-11-16; 08, 09 and 11 on 2026-11-18. Every
`story.yaml` changed on 2026-11-24.

A cross-project benchmark should give, per project, one row with:
headline metric + unit + split + n, baseline value and delta, CI method (per
`docs/engineering/statistical-intervals.md`), how many times the test/sealed
window was read (to expose reuse like 02's erratic gate and 01's final_v3),
the committed source path, last reproduced date and git SHA (`_meta` blocks),
wall-clock and cost of `dvc repro` or the eval, and whether the headline guard
covers it. Generate it from committed metrics only (no reruns) into
`docs/projects/index.md` or a new `docs/engineering/benchmark.md`, with a
`--check` mode like the other generators. Owner approval is required for a
new script and page (D8).

---

## 6. Prioritized task list for Kimi (max 15)

| # | task | files to touch | acceptance check | owner approval? |
|---|---|---|---|---|
| 1 | **Fix judge-calibration attribution** (C1): replace "owner hand-labelled / owner-validated / blind" with the true state ("model labels audited 30/30 by a reviewer agent; owner hand-label pending"), or hold until V2 is done | `projects/01-rag-agent/README.md:9,72-74,95`; `story.yaml:2,222-225,280,374,458,506`; `docs/projects/01-rag-agent.md:5,13,87,179`; `apps/showcase-web/src/lib/cardCopy.ts:45`; then regenerate `storyShort.ts` via `gen_story_short.py` | `git grep -n -i "owner.*\(hand-label\|blind\|validated\)\|30/30 blind" projects/01-rag-agent docs/projects apps/showcase-web/src/lib` returns only truthful wording; `check_short_copy.py --check` and `gen_story_short.py --check` pass | **yes** (wording, or wait for V2) |
| 2 | **Fix faithfulness CI** (C2) after V1 re-aggregation confirms `[0.8092, 0.9304]` | `projects/01-rag-agent/README.md:92`, `story.yaml:372`, `docs/projects/01-rag-agent.md:84` | each value appears verbatim in `reports/final_v3_e2e/metrics.json` | no (truth fix) |
| 3 | **V1 offline re-aggregation** of final_v3 (5.5) | none (read-only); write results to the close-out only | `--summarize` output equals the committed `f1_summary.json`; CIs recorded | no |
| 4 | **Extend the headline guard to 01**: add an extractor for `final_v3_e2e/f1_summary.json:f1` (0.9091) and S3 `recall_at_5` (0.946), and remove `uncovered:01-rag-agent` | `scripts/check_headline_numbers.py:15-17,32,+extractor`; `scripts/tests/test_check_headline_numbers.py` | `check_headline_numbers.py` reports 13 claims, 0 findings; a test covers 01 | no |
| 5 | **Regenerate RAG figures from final data** (5.4 items 1-4, 8): taxonomy (n=120), retrieval ladder, final outcome, verify funnel; rewrite captions | `projects/01-rag-agent/src/rag_agent/figures.py` (only if a new builder is needed), a small build script under `projects/01-rag-agent/scripts/`, `reports/figures/*.json`, `story.yaml:207,339,513-522` | figure JSON numbers equal `final_v3_e2e/metrics.json` and the sweep files; `lint_story_language.py` 0 errors; web `PlotlyFigure`/`plotlyToECharts` tests pass | partly (Wave 6 Part A approved; a new figure set or names needs a nod) |
| 6 | **Static PNG refresh** (5.4 items 6-7): retarget the README hero and docs figures, prune orphan entries | `scripts/export_readme_figures.py:26-52`, `docs/assets/readme/rag-quality-cost-frontier.png` (rename if the subject changes), `docs/assets/projects/01-rag-agent/*`, `README.md:36`, `docs/projects/01-rag-agent.md:99` | `check_docs.py` OK; `mkdocs build --strict` OK; the PNG visually matches the JSON | yes (hero choice) |
| 7 | **Fix 02 copy** (C9, C10): the erratic paragraph states the full-panel test score 0.6235, delta +0.0025 ≈ 3.9× the noise band, and that the adoption check used the test window; 57.3% → 57.2% | `projects/02-demand-forecasting/story.yaml:243-255,284-291,287,338,385` (and README or docs if they mirror it) | every number traces to `reports_m5_full/metrics.json`; `check_headline_numbers.py` OK; story lint OK | **yes** (changes the "scored once" narrative) |
| 8 | **Remove traffic-light dots in all three apps** (4.1) | showcase-web `src/components/Terminal.tsx:3,8-12`, `src/styles/shell.css:178-201`; agent-chat `web/src/components/chat/ChatSurface.tsx:46-50`, `web/src/styles.css:183-206`; document-intelligence `web/src/App.tsx:25`, `web/src/styles.css:118-121,364` | `git grep -n "terminal-dots" apps` returns nothing; each app's `npm test && npm run lint && npm run build` pass; titlebar visually OK at 375px and 1440px | no (owner asked) |
| 9 | **Demo and card sizing, proposal A** (4.3) | `apps/showcase-web/src/styles/cards-grids.css:4-17,215-227,301-309`; optionally `.study-card__content` | existing `ProjectsIndex.test.tsx` assertions still pass; Playwright screenshots at 375/768/1280/1440/1920/2560 (in `artifacts/`) show demo cards ≤ ~570px and no horizontal scroll | no for A; **yes** for B or ≥3 project columns |
| 10 | **Workbench bounds on large screens** (4.3) | `apps/showcase-web/src/styles/demos.css:292-312,465-475`, `demos-workbench.css:301-307,505,623` | `ChurnSandbox`/`ForecastWorkbench` tests pass; at 2560 the chart is ≤ ~1,400px wide; mobile layout unchanged at 375 | no |
| 11 | **Re-capture app media** after #8: document-intelligence via the local fixture script; agent-chat per D3; sync the docs copies with the web copies | `apps/showcase-web/public/apps/*-v3.png`, `agent-chat-demo.{webm,mp4}` (+ `.vtt` if the timing changes), `document-intelligence-{summary,qa}.png`, `docs/assets/apps/*.png` | no dots visible; `AppNavigation.test.tsx` passes; docs and web images are identical (md5) | **yes** (D3: hosted vs mock recording) |
| 12 | **Delete dead media** | `apps/showcase-web/public/apps/agent-chat-{ui,approval,memory}{,-v2}.png` (6); orphan `docs/assets/projects/{01…/failure_taxonomy,02…/forecast_vs_actual,02…/metrics_bars,04…/epochs_probe,05…/cost_surface,11…/normalized_heatmap}.png` | grep for each basename over `apps docs README.md projects/*/README.md projects/*/story.yaml scripts` returns nothing; `check_docs.py` OK | **yes** (deletion) |
| 13 | **Scrub absolute home paths** (P4) from committed evidence | writers in `projects/01-rag-agent/scripts/build_final_v3.py` (file-access logger) and the 02 `m5_full` report/metadata writers; then regenerate `reports/final_v3_file_access.json`, `reports_m5_full/*`, `reports_m5/*` | `git grep -c "/Users/" -- projects` = 0; `check_demo_contract.py` and `check_headline_numbers.py` OK | **yes** (evidence artifacts) |
| 14 | **Env and compose hygiene**: `web-dev` anonymous `node_modules` volume; align the healthcheck on `/ready`; document the arm64 node requirement | `docker-compose.yml:17,27-28`; `apps/showcase-web/README` or `AGENTS.md` dev note | `docker compose config` valid; `npm ci && npm test` pass on arm64 node | no |
| 15 | **Em-dash pass** on the top offenders (3.3), one file per commit-sized step | `projects/{06,04,02,11}-*/README.md`, `docs/projects/{09,01,10}-*.md`, `docs/apps/chatbot-agent.md` | the prose `" — "` count falls under 8 per file; `check_short_copy.py --check`, `lint_story_language.py`, `check_docs.py` OK; no numbers changed (diff review) | no |

Deferred (not in the 15): cross-project benchmark generator (5.6, D8); the
01 `reports/metrics.json` refresh (D5); `reports/axe.json` tracking (2.1);
splitting files over 1,000 lines (1.4).

---

## 7. Owner decisions needed

| id | decision | context |
|---|---|---|
| D1 | Hand-label the 30-item `owner_sample.json` now (V2)? Until then, which interim wording goes public (task 1)? | 5.3, C1 |
| D2 | Add a disclosure that final_v3 retrieval was read 3× and gated the S3 promotion, and declare final_v3 consumed (new sealed final_v4 for future work)? | 5.2 |
| D3 | Agent-chat re-record: hosted Kimi (quota), local Ollama, or `VITE_MOCK=1` with a caption that says scripted? | 4.2 |
| D4 | Approve V3 (owner labels about 40 real final_v3 claims) and/or V4 cross-judge (local $0 vs hosted budget)? | 5.5 |
| D5 | Refresh 01 `reports/metrics.json` to final values (conventions) or keep it frozen at wave-14 and point the guard at `final_v3_e2e/`? | C7 |
| D6 | Approve the 02 erratic-paragraph rewrite that admits a second use of the test window | C9 |
| D7 | Demo/project grid: proposal A (cap, keep 2 columns) or B (auto-fill, 3+ columns on wide screens, reversing the earlier 2-column decision)? | 4.3 |
| D8 | Build the cross-project benchmark page and generator? | 5.6 |
| D9 | Delete 6 dead web PNGs and 6 orphan docs PNGs; keep or drop committed review screenshots (7.8 MB) and `reports/axe.json` | 2.1, 2.3, 2.5 |
| D10 | Rewrite committed evidence files to strip absolute paths | P4 |
| D11 | README hero figure for RAG: retrieval ladder, final outcome, or keep a (relabelled) frontier? | 5.4 item 6 |

---

## 8. Gate and verification commands for Kimi

Run from repo root unless noted. All of these are local and need no hosted calls.

```bash
# environment (arm64 node; fixes the rollup optional-dep mismatch)
node -p "process.arch"                      # must print arm64
cd apps/showcase-web && npm ci && cd ../..

# python
uv sync --all-packages --dev
uv run ruff check . && uv run ruff format --check .
uv run mypy libs projects apps
HF_HUB_OFFLINE=1 uv run pytest -q
(cd projects/01-rag-agent && HF_HUB_OFFLINE=1 uv run pytest --cov)

# repo checks
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/check_headline_numbers.py
uv run python scripts/lint_story_language.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict

# web
(cd apps/showcase-web && npm test && npm run lint && npm run build)
(cd apps/agent-chat && uv run ruff check . && uv run mypy src tests && uv run pytest -q && cd web && npm test && npm run build)
(cd apps/document-intelligence && uv run ruff check . && uv run mypy src tests && uv run pytest -q && cd web && npm test && npm run build)

# targeted verifications
git grep -n "terminal-dots" apps                                  # expect: no output
git grep -c "/Users/" -- projects                                 # expect: no output (after task 13)
git grep -n -i "owner hand-labelled\|owner-validated\|owner blind" -- projects docs apps/showcase-web/src   # expect: none until V2 done
python3 -c "import json;print(json.load(open('projects/01-rag-agent/reports/final_v3_e2e/metrics.json'))['detail']['final_v3']['faithfulness'])"
```

Visual check (task 9/10/11): Playwright screenshots of `/projects`,
`/demos/forecast-workbench`, `/demos/churn-sandbox`, `/`, `/glossary` at
widths 375, 768, 1280, 1440, 1920, 2560, in light and dark, saved under
`artifacts/` (gitignored). Attach paths in the close-out, not the images.

Close-out location for Kimi: `collaboration/reviews/20261124-wave6/00-closeout.md`
(as named in the Wave 6 handoff). Report exact files, gate output and the
viewport screenshot paths. No commits or pushes.
