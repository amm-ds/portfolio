# Design brief: portfolio pass before the new projects (wave 7 prerequisite)

Date: 2026-11-24
Designer: Claude Code (design lane; no implementation files edited)
Owner: session owner
Status: **draft, pending owner approval.** Kimi must not start from this package until the status reads `approved`.
Related artifacts:
- `collaboration/designs/20261124-wave65-ui-and-rag-article-polish/01-design-and-handoff.md` (untracked draft from a parallel session; overlaps Track A, B, C. This package verifies it and supersedes it where noted in `02-architecture-proposal.md`.)
- `collaboration/designs/20261124-next-experiments/` (approved wave 7 plan; unchanged by this pass)
- `docs/engineering/repo-conventions.md`

Legend: **[V]** verified in this session by reading a file, running a script, or reading a committed artifact on 2026-11-24. **[I]** inference, to be confirmed by the owner or by a measurement at implementation time.

## 1. Problem

The owner asked for four fixes, in this order, before wave 7 projects start:

1. **/projects cards are centered instead of full width.** A regression from the last wave. [V] Owner report, relayed in the task.
2. **Demo card sizes still look wrong after the last change.** [V] Owner report. The owner's screenshot is not visible to the design session. **Blocked on owner input** (see section 6).
3. **Experiment articles** (`projects/*/story.yaml`, rendered by `CaseStudy` and `StorySection`) should follow the owner's section pattern: an introduction with the diagram, the contents as bullets, and a closing with tables or visualizations and a link to the next step. Pilot: RAG project 01. [V] Owner guideline, as recorded in the wave 6.5 draft, `01-design-and-handoff.md` §2.
4. **Roadmap** (`RoadmapBlock` and the story `roadmap:` cards) should use clearer, neutral, high-level milestones, validated with the owner before implementation. [V] Owner request.

## 2. Success criteria

- SC1: At 1280, 1920 and 2560 px wide, `.project-grid`, `.demo-grid` and `.apps-grid` span the same width as the page content (`.app-main--fluid`, no cap). No grid rule in `cards-grids.css` carries `max-width` or `margin-inline: auto`.
- SC2: The demo-card size fix is specified against a named viewport and a named screenshot, not guessed. Until then the design lists the causes found in code (section 4) and does not ship a speculative change.
- SC3: The RAG 01 story keeps its eight section ids in fixed order and its `short_version` (≤280 chars). Every number in the rewritten copy is traceable to a committed artifact. `scripts/lint_story_language.py` reports 0 errors and no new warnings. `scripts/check_short_copy.py --check` passes.
- SC4: The RAG 01 roadmap has 3–4 `shipped` cards and 1 `next` card, title 3–6 words, verb-first, no metric, detail ≤90 chars, and the owner has confirmed the wording.
- SC5: Gates named in `AGENTS.md` pass for every touched surface (section 7 of the handoff).

## 3. Non-goals

- No new project pages, no wave 7 implementation, no changes to `projects/13-*` or to the approved wave 7 design.
- No rewrite of projects 02–13 in this pass. Pilot on 01, owner review, then rollout is a separate decision (open question Q4).
- No change to the API, the registry contract, or the demo registry endpoint.
- No git mutations. The owner commits.

## 4. Findings

### 4.1 Projects page regression (item 1)

Cause: wave 6 (commit `214cc041`, "fix wide viewports") added `max-width: 72rem` (1152 px) and `margin-inline: auto` to the three card grids. [V] `git show 214cc041 -- apps/showcase-web/src/styles/cards-grids.css`.

- `.demo-grid`: `margin-inline: auto; max-width: 72rem;` at `apps/showcase-web/src/styles/cards-grids.css:10-11`.
- `.project-grid`: `margin-inline: auto; max-width: 72rem;` at `cards-grids.css:223-224`.
- `.apps-grid`: `margin: 0 auto 2rem; max-width: 72rem;` at `cards-grids.css:256-257`.

The page container does not cap width. `App.tsx:142` renders `<main class="app-main app-main--fluid">`, and `.app-main--fluid` sets `max-width: none` at `apps/showcase-web/src/styles/tokens-base.css:240-241`. The page header, the topic rows and the index are therefore full width, while the grids are centered in a 1152 px column. On any viewport wider than about 1190 px (1152 px plus the 1.25rem side padding) the cards get gutters on both sides. This matches the owner report. [V]

Existing tests do not pin the cap. `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx:302-325` checks `grid-template-columns: 1fr` and `repeat(2, minmax(0, 1fr))`, not `max-width`. So the regression passed the gate. [V]

### 4.2 Demo card sizing (item 2): causes found in code, screenshot needed

Candidates, ranked by how likely they explain "demo cards look the wrong size":

a. **Same 72rem cap on `.demo-grid`** (`cards-grids.css:10-11`). The demo cards share the cap from 4.1, so they are centered too. Fixing 4.1 fixes this part.

b. **`.study-card__content { max-inline-size: 70ch; }`** (`cards-grids.css:48-51`, added in wave 6). The text column is capped at about 70 characters, while the card itself can be much wider. On wide screens each card has a dead right-hand area. This applies to project cards and demo cards. The cap is a reasonable reading width, but it was added as part of a "proposal A" that was not verified against a screenshot. [I]

c. **Workbench shell on `/demos/forecast-workbench`** (the owner may mean these cards or KPI tiles):
   - `.wb-root` uses six `auto` rows with `min-height: calc(100dvh - 58px - 1rem)` and no `align-content` (`apps/showcase-web/src/styles/demos.css:300`, `:310`). On tall or wide viewports the leftover height is spread across the auto rows, which stretches the header, the "more information" block, the KPI band and the notice strip. [I, consistent with the wave 6.5 draft §Track A.2; not yet reproduced]
   - `.wb-root` also has `max-width: 109rem; margin-inline: auto;` (`demos.css:313-314`), which centers the workbench on 2560 px screens.
   - `.wb-notice-strip` uses `grid-template-columns: 1fr 1fr` (`demos.css:443`), leaving an empty half when one notice renders.
   - `.wb-canvas-slot .figure-card` uses `min-height: clamp(400px, 48vh, 640px)` and `demos-workbench.css` changed a 3-column block from `280px` to `clamp(240px, 24vh, 360px)` (wave 6, `git show 214cc041`). Both depend on viewport height. [V]

Without the owner's viewport and screenshot, the fix cannot be chosen between (a)+(b) and (c). The owner must answer Q1 and Q2 in `OPEN_QUESTIONS.md`.

### 4.3 Experiment article structure (item 3)

Current state of `projects/01-rag-agent/story.yaml` [V, read in full for sections, word counts from `lint_story_language.py`]:

- Eight sections in fixed order: background, objectives, data, eda, training, evaluation, results, conclusions (`story.yaml:4-…`). Contract holds.
- `short_version` is 259 chars (`story.yaml:2`). Limit 280. [V]
- Diagrams are already present in the introductions: `background` embeds `01-rag-pipeline` (`story.yaml:12`), `objectives` embeds `auto-01-rag-agent-1` (`story.yaml:33`). Other sections embed diagrams in their bodies. [V]
- Bullets: the lint reports the `evaluation` section at 685 words against a soft 550-word budget (`scripts/lint_story_language.py:64`). The wave 6.5 draft says `evaluation` and `results` have no bullet lists. Confirm before rewriting: `grep -n "^ *- " projects/01-rag-agent/story.yaml` returns the bullets to be counted. [I until counted]
- Closing: `**In plain terms:**` is the rendered takeaway marker (`apps/showcase-web/src/components/StorySection.tsx:8-9`). Legacy `**Business summary:**` still renders. [V]
- Truth in copy: headline numbers are traced in section 4.4.

The owner's target is engaging, technical but plain-language, not verbose, and not shy about technical depth. The rules are in `02-architecture-proposal.md` §3.

### 4.4 Truth-in-copy trace for RAG 01 headline numbers [V]

`repo-conventions.md` says numbers must exist in `reports/metrics.json` "or another committed artifact." The check is per artifact, so the trace below records where each headline number lives.

| Claim in copy | Value | Committed source |
|---|---|---|
| 593 Wikipedia articles | 593 | `projects/01-rag-agent/reports/experiment_log.json`, `final_v3_file_access.json` |
| S3 recall@5 on final_v3 | 0.9457 (from R0 0.9239) | `reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`, `reports/retrieval_baseline/final_v3.json`, `reports/figures/retrieval_ladder.json` |
| final_v3 F1 / precision / recall | 0.9091 / 0.9524 / 0.8696 | `reports/experiment_log.json` (lines around 5136) |
| final_v3 faithfulness | 0.8717 | `reports/final_v3_e2e/metrics.json`, `reports/experiment_log.json` |
| 1/120 unsupported claim | 1 | `reports/experiment_log.json` (final pass) |

**Finding:** `reports/metrics.json` itself does not carry these final_v3 headlines. Its `rag_agent` block holds an older run (`faithfulness` 0.6209, `answer_relevance` 0.6458, `metrics.json` `rag_agent`). The convention is met by "another committed artifact", but the headline guard `scripts/check_headline_numbers.py` may read only `metrics.json`. The handoff does not change this; it is an open question (Q5).

## 5. Recommendation summary

1. Remove the three 72rem caps (grids span the page width). Keep the 2-column grid from 720 px. Smallest change, reverts the regression, no new contract. [Architecture §2]
2. Demo sizing: apply 1 now. Decide b and c only after the owner's screenshot (Q1, Q2). [Architecture §2.3]
3. RAG 01 article: pilot the section pattern on project 01 only, keep ids, `short_version`, figures and eight sections. Owner reviews the rewritten text before rollout. [Architecture §3]
4. Roadmap: replace RAG 01 cards with the neutral milestone set in Architecture §4, after the owner confirms the wording (Q3). Keep 4 shipped + 1 next.

## 6. Open questions

See `OPEN_QUESTIONS.md` in this directory. Blocking: Q1 (viewport and screenshot), Q2 (which demo cards: `/projects#demos` or the workbench), Q3 (roadmap wording). Non-blocking: Q4 (rollout beyond RAG 01), Q5 (headline numbers in `metrics.json`).
