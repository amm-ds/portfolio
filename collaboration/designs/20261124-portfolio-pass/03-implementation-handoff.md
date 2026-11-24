# Implementation handoff: portfolio pass (grids, demo sizing, RAG 01 article, roadmap)

Date: 2026-11-24
Status: **draft. Not approved. Kimi must not start until the owner sets `Status: approved` and Q1–Q3 in `OPEN_QUESTIONS.md` are answered or the default applies.**
Design: `01-design-brief.md`, `02-architecture-proposal.md`.
Executor: Kimi Code. Owner commits. No git mutations by agents.

## 0. Preconditions

- Work in `~/work/portfolio` on `main` (or the branch the owner names). Working tree clean except this design directory.
- `uv sync --all-packages --dev` and `cd apps/showcase-web && npm ci` if dependencies are missing. On macOS arm64, see `AGENTS.md` (Rollup note).
- Baseline before edits: `uv run python scripts/lint_story_language.py` → 0 errors, 1 warning (`01-rag-agent evaluation 685 words`). Record the output.

## 1. Affected files

| File | Change | Step |
|---|---|---|
| `apps/showcase-web/src/styles/cards-grids.css` | remove `max-width`/`margin-inline` from `.demo-grid`, `.project-grid`, `.apps-grid` | 1 |
| `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx` | add no-cap assertions | 2 |
| `apps/showcase-web/src/styles/demos.css` | §2.3(c) only if Q2 = workbench: `.wb-root`, `.wb-notice-strip` | 3 (gated) |
| `apps/showcase-web/src/styles/cards-grids.css` `.study-card__content` | §2.3(b) only if Q1 says so | 3 (gated) |
| `projects/01-rag-agent/story.yaml` | rewrite section prose per `02-architecture-proposal.md` §3; roadmap per §4.2; keep ids, order, `short_version`, figures | 4, 5 |
| `apps/showcase-web/src/__tests__/StorySection.test.tsx`, `CaseStudy.test.tsx`, `RoadmapBlock.test.tsx` | update only if a test pins changed copy or roadmap titles | 6 |

Not touched: `short_version`, `src/lib/storyShort.ts` (generated), `src/lib/staticRegistry.ts` (generated; `has_roadmap` flag only, still true), `projects/*` other than 01, `apps/showcase-api`, `libs/`.

## 2. Ordered steps

### Step 1: remove the grid caps (no gate on owner input)

In `apps/showcase-web/src/styles/cards-grids.css`:
- `.demo-grid` (lines 5–13): delete `margin-inline: auto;` and `max-width: 72rem;`. Also update the comment at lines 3–4 (remove "capped so the two demo cards stay readable on very wide screens (proposal A)").
- `.project-grid` (around lines 219–226): delete `margin-inline: auto;` and `max-width: 72rem;`.
- `.apps-grid` (around lines 253–259): change `margin: 0 auto 2rem;` to `margin: 0 0 2rem;` and delete `max-width: 72rem;`.

Do not change `grid-template-columns` or the 720 px / 960 px breakpoints.

Verify: `grep -n "72rem" apps/showcase-web/src/styles/cards-grids.css` returns nothing.

### Step 2: pin the regression in tests

In `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx`, add a test next to the "2-column project-grid" test (around line 302–325):
- Read `stylesCss`, extract the `.project-grid`, `.demo-grid` and `.apps-grid` rule bodies with the same regex style the file already uses.
- Assert none contains `max-width` or `margin-inline: auto`.

Run: `cd apps/showcase-web && npm test -- ProjectsIndex`. Must pass.

### Step 3: demo sizing (gated)

Only after Q1 (viewport and screenshot path) and Q2 (which demo surface) are answered.
- If Q2 includes `/demos/forecast-workbench`: apply §2.3(c) of the architecture proposal to `demos.css` (lines 293–316 and 441–445). Add a test in `ProjectsIndex.test.tsx` or a new `demos` CSS test only if an existing style test pattern covers `demos.css`; otherwise verify visually (step 7).
- If Q1 asks for the text cap change: apply §2.3(b) to `.study-card__content` (`cards-grids.css:48-51`) or scope it to `.demo-card`.
- If neither is answered: skip, and list demo sizing as "open, awaiting screenshot" in the completion report.

### Step 4: rewrite RAG 01 prose (pilot)

In `projects/01-rag-agent/story.yaml`, rewrite the `text_md` of the eight sections, following `02-architecture-proposal.md` §3.2:
- Keep section ids and order; keep `figures:` lists and `metrics_keys:` lists unless a figure or table moves.
- Keep `short_version` byte-identical.
- Each section: bold hook, 2–3 plain sentences, diagram block (existing), 3–5 bullets, evidence reference, one bridge sentence, then exactly one `**In plain terms:**` paragraph as the last block.
- Move development history (65q, 55q, 30q, set B, stress runs, legacy latency) to `conclusions` under `## Exact numbers` or to `DESIGN.md`. Do not leave them in visible `results`.
- Show only the final sealed pass as current results. Add refusal accuracy 0.857, false-abstention rate 0.120 and latency p50 16.5 s / p95 40.5 s from `projects/01-rag-agent/reports/final_v3_e2e/metrics.json` if they are shown; cite the file in the nearby text.
- Replace "empty-answer" with "unnecessary refusal" in prose (one short definition).
- Background opening: ≤140 raw words including bullets (lint hard limit is 150).
- Targets: evaluation ≤550 words; results ≤400; training ≤500.
- No repository paths in prose.
- Every number in the new prose must match the committed artifact listed in `01-design-brief.md` §4.4 or `02-architecture-proposal.md` §5. If a number cannot be traced, remove it; do not invent.

Verify after editing:
```bash
uv run python scripts/lint_story_language.py          # 0 errors; warnings only for conclusions if any
uv run python scripts/check_short_copy.py --check     # short_version unchanged, still passes
uv run pytest -q projects/01-rag-agent/tests/test_schemas.py projects/01-rag-agent/tests/test_platform_contracts.py
```
If `test_schemas.py` or `test_platform_contracts.py` pins section text, update the test only to match the new copy and note it in the completion report.

### Step 5: roadmap (after owner confirms wording, Q3)

Replace `projects/01-rag-agent/story.yaml` `roadmap:` block (lines 523–538) with the cards in `02-architecture-proposal.md` §4.2. Keep 4 `shipped` + 1 `next`.

Before writing: confirm the source of "10 of 92" (false-abstention count). If it cannot be traced, change the `next` detail to a number that can, or to a decision ("Gate: a fresh sealed set chosen before tuning."). Report which.

Verify:
- Each detail ≤90 chars: `uv run python -c "import yaml;[print(len(r['detail']),r['title']) for r in yaml.safe_load(open('projects/01-rag-agent/story.yaml'))['roadmap']]"`
- `cd apps/showcase-web && npm test -- RoadmapBlock` (update the test only if it pins RAG titles; the current test uses fixture data).

### Step 6: web tests touching changed copy

`cd apps/showcase-web && npm test -- StorySection CaseStudy RoadmapBlock`. Fix only assertions that pin the old copy.

### Step 7: gates (full, before reporting)

From repo root:
```bash
uv sync --all-packages --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run pytest -q
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
```
From `apps/showcase-web`:
```bash
npm ci && npm test && npm run lint && npm run build
```
Visual check (optional but requested for step 1): run `npm run dev` (port 4321) and the API `uv run uvicorn showcase_api.main:app --port 8000`; capture `/projects` at 1280 and 1920 and 2560 px and confirm the cards span the page width. Use the built-in browser if available; record the screenshot paths in the completion report. Do not commit screenshots.

If `gen_static_registry.py --check` fails because the roadmap change altered `has_roadmap` or other summary fields, run `uv run python scripts/gen_static_registry.py` (regenerate, do not hand-edit) and report the diff.

### Step 8: completion report

Write `collaboration/reviews/20261124-portfolio-pass/00-closeout.md` with: files changed; step-by-step pass/fail; the lint output before and after; the demo sizing status (done / skipped with reason); any test assertion changes and why; open items.

## 3. Acceptance criteria

- AC1: no `max-width` or `margin-inline: auto` on `.project-grid`, `.demo-grid`, `.apps-grid`; new test passes.
- AC2: `/projects` cards span the page width at 1280/1920/2560 px (visual check recorded).
- AC3: RAG 01 has the eight ids in order; `short_version` unchanged; `lint_story_language.py` 0 errors and no new warnings; `check_short_copy --check` passes.
- AC4: every number in changed RAG 01 copy traces to a committed file (list them in the closeout).
- AC5: roadmap: 4 shipped + 1 next, titles 3–6 words verb-first without metrics, details ≤90 chars; owner-confirmed wording (Q3).
- AC6: all gates in §2 Step 7 pass, or failures are reported verbatim with cause.

## 4. Known risks

- Demo sizing may be unfixed until the screenshot arrives (Q1/Q2).
- Opening-section lint limit (150 raw words) can be tipped by added bullets; rule in Step 4.
- "10 of 92" roadmap figure may not be traceable (Step 5 check).
- `metrics.json` does not hold the final_v3 headline numbers (Q5); the closeout must name the committed source for each.
- Removing the grid cap makes 2-column cards wide on 2560 px screens (Q1).

## 5. Out of scope

Projects 02–13 article rewrite; wave 7 projects; `apps/agent-chat`; `apps/document-intelligence`; API; registry; git commits.
