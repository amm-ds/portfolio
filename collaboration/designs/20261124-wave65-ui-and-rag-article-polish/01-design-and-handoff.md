# Wave 6.5 Design & Handoff — UI Grid/Workbench Sizing Fix + RAG Article & Roadmap Polish

Date: 2026-11-24
Authors: Claude Code + Neon Reviewer
Status: Pending owner validation (Track A UI fix ready for Kimi; Track B RAG pilot awaiting owner sign-off before rollout to 02–13)

---

## 1. Track A — UI Regressions (Projects Grid, Demos Grid, and Forecast Workbench)

### Root Causes Diagnosed (Verified in CSS + Owner Screenshot)
1. **`/projects` and `/demos` cards centered instead of full container width:**
   - `apps/showcase-web/src/styles/cards-grids.css` lines `10-11` (`.demo-grid`), `223-224` (`.project-grid`), and `256-257` (`.apps-grid`) added `max-width: 72rem; margin-inline: auto;`.
   - Because `.app-main--fluid` (`tokens-base.css:240-241`) has `max-width: none`, capping the grids at `72rem` (`1152px`) centered the cards in a narrower column than the full-width page headers and tables.
2. **Demand Forecast Workbench tall hollow KPI/info cards & centered strip:**
   - `apps/showcase-web/src/styles/demos.css` lines `300, 310` set `.wb-root` to `grid-template-rows: auto auto auto auto auto auto;` alongside `min-height: calc(100dvh - 58px - 1rem);` **without `align-content: start`**. On tall/wide viewports (e.g., 2560px), CSS Grid distributes leftover `min-height` equally across all 6 `auto` rows, stretching `.wb-header`, `.wb-evidence` (`> more information`), `.wb-kpi-band` (all 3 KPI cards), and `.wb-notice-strip` into tall hollow boxes.
   - `demos.css:313-314` also set `max-width: 109rem; margin-inline: auto;`, centering the workbench on 2560px displays.
   - `demos.css:443` sets `.wb-notice-strip` to `grid-template-columns: 1fr 1fr`, leaving an empty right half when only 1 notice is rendered.

### Exact CSS Fixes (`apps/showcase-web/src/styles/`)
1. **`cards-grids.css`:**
   - Remove `max-width: 72rem; margin-inline: auto;` from `.demo-grid`, `.project-grid`, and `.apps-grid` so all three span the full `.app-main--fluid` width cleanly (keep `.study-card__content { max-inline-size: 70ch; }` for readable text lines inside cards).
   - For `.demo-grid` on wide screens (`>= 1400px`), optionally keep 2 columns spanning full width or `repeat(auto-fit, minmax(420px, 1fr))` so cards align flush with `/projects` below.
2. **`demos.css`:**
   - On `.wb-root`: add `align-content: start;`, remove `min-height: calc(100dvh - 58px - 1rem);` (or rely on `align-content: start` + `height: auto`), and remove `max-width: 109rem; margin-inline: auto;` (or use `max-width: none;`) so top header, `> more information`, KPI cards, and notice strip stay compact at their natural content height and align edge-to-edge.
   - On `.wb-notice-strip`: change `grid-template-columns: 1fr 1fr` to `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` so a single notice spans full width cleanly.
3. **Verification:** Re-run `npm test && npm run lint && npm run build` in `apps/showcase-web` and capture Playwright screenshots at `1280` and `2560` on `/projects`, `/demos`, and `/demos/forecast-workbench` confirming zero vertical card bloat and full-width alignment.

---

## 2. Track B — Experiment Articles Structure & Language (Pilot: `01-rag-agent`)

### Diagnosis of Current `projects/01-rag-agent/story.yaml`
- **`evaluation` (685 words) triggers `lint_story_language.py`'s 550-word soft budget warning**; `results` is 543 words.
- Both `evaluation` (8 consecutive paragraphs) and `results` (7 consecutive paragraphs) have **zero bullet lists**, packing 4-decimal numbers, Wilson CIs, and legacy dev runs (`65q`, `55q`, `30q`, `set B`) into dense prose walls.
- `background` opens with insider shorthand (`Independent set B has 9 unsupported-claim outcomes`, `final_v3`) before explaining plain-English stakes.
- Uses legacy `**Business summary:**` marker instead of `**In plain terms:**` (`StorySection.tsx:8-11`).

### Target Section Pattern (Applied to `01-rag-agent` Pilot, Then Template for `02–13`)
Every section follows one scannable, engaging rhythm aimed at both technical and non-technical readers:
1. **Introduction (+ Diagram / Visual):** Bold lead hook + 2–3 plain-English sentences establishing the problem/choice, paired immediately with the section's diagram (`01-rag-pipeline`, `auto-01-rag-agent-1..4`) or key chart.
2. **Structured Bullet Points:** 3–5 crisp bullets highlighting the core engineering decisions, mechanisms, and trade-offs (showcasing real technical depth—hybrid RRF, cross-encoder reranking, tool-budget rails, Wilson/bootstrap intervals—in accessible terms).
3. **Tables & Visualizations + Transition:** Reference the section's `StoryMetricsTable` (`metrics_keys`) or right-column `FigureCard` charts, followed by a 1-sentence bridge linking to the next section.
4. **Plain-Language Takeaway Card:** End with `**In plain terms:**` (1–2 crisp sentences).
5. **Word Budgets:** Trim `evaluation` from 685 to ~320–350 words and `results` from 543 to ~320–360 words by moving granular multi-pass/4-decimal tables into `conclusions -> ## Exact numbers` (already collapsed in `<details>`).

---

## 3. Track C — Neutral Milestone Roadmap (Pilot: `01-rag-agent`)

Replaced overly granular counts/internal IDs (`final_v3`, `judge_v2`, `S3`, `12/16/200k`, `10/92`) with neutral, high-level development milestones on the 5-card `Data -> Training -> Evaluation -> Production -> Next` arc (`title` 3–6 words verb-first, `detail <= 90` chars):

```yaml
roadmap:
- status: shipped
  title: "Build pinned domain corpus"
  detail: "Curate bounded Wikipedia articles and locked evaluation splits."
- status: shipped
  title: "Develop hybrid retrieval pipeline"
  detail: "Combine dense embeddings, lexical search, and cross-encoder reranking."
- status: shipped
  title: "Validate grounding and judge audit"
  detail: "Calibrate automated claim verification against audited golden samples."
- status: shipped
  title: "Harden bounded agent execution"
  detail: "Add tool-budget limits, claim repair loops, and checkpointed runs."
- status: next
  title: "Reduce false abstentions on edge cases"
  detail: "Tighten retrieval and repair rails to cut unnecessary empty answers."
```

Once the owner validates this tone and structure on `01-rag-agent`, roll the same neutral milestone style out across `02–13`.
