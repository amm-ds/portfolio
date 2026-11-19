# UI and apps fixes: review and handoff

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code (owner runs it)
Owner: amm-ds
Status: H1–H8 APPROVED by owner on 2026-11-19. Defaults applied where the owner did not choose: H6 uses option (a), a 2×2 grid below the breakpoint; the agent-chat table in H5 is a summary by case kind, not the full 16-case table.

## 0. Scope of this pass

Checked in the live site (alejandromerida.dev, production build, not the local uncommitted changes) at 375 px and in the code:
- Projects page order, section titles and subtitles.
- The apps articles (document-intelligence, agent-chat): tables and section titles.
- The `nab_tune_surface` figure in project 03, and the mobile flow diagrams.

Not covered in this pass: the per-project article and results review across all 13 projects. That is a separate, larger pass (section 5). Production may lag the local tree, so re-check after the owner deploys.

## 1. Findings

### F1. Projects page order is wrong
- Current: `apps/showcase-web/src/pages/ProjectsIndex.tsx` renders `apps` (line ~368), then `DemosSection` (line ~377), then `experiments` (line ~387). The anchor nav (line ~351) lists apps, live demos, then experiment rows.
- Wanted: apps, experiments, demos.

### F2. Article section titles render as "01Background"
- Seen on `/apps/document-intelligence` and `/apps/agent-chat`: the heading text reads "01Background" with no space. Wanted: "01 Background" (the request says remove the "/" and keep the number).
- Find the rule that renders the index prefix (the number and separator) in `ArticleSection` / `AppArticleSection` and fix the spacing there, not per page.

### F3. Section subtitles are blue; they should be gray
- Subtitle styling in the article section components. Change to the existing muted-text token, in both light and dark themes.

### F4. Missing and malformed tables in the apps articles
- **document-intelligence, section 07 Evaluation:** the table "Committed live result — 2026-11-08" is rendered as a raw `<table>` inside `div.prose` (`pages/DocumentIntelligenceArticle.tsx` line ~344). It has no `data-table` class and no `table-scroll` wrapper, so it renders without the table styling and can overflow at 375 px (measured: 335 px wide, no wrapper). Fix: render it through the shared markdown table path (`lib/markdown.tsx` pipe tables), or give it the same class and wrapper.
- **agent-chat, section 06 Evaluation:** the page has no table at all (0 tables on the live page). The measured report `apps/agent-chat/reports/evals-kimi-for-coding.md` has a per-case table (case, kind, grader, verdict). The article should show a summary table from that report (count of passes per case kind, and the 108/108 total). Build it from the committed report, not by hand.

### F5. Project 03: `nab_tune_surface` overlaps at narrow widths
- The figure is four subplots side by side in one row (`projects/03-anomaly-detection/src/anomaly_detection/nab_tune.py`, `tune_figure`, `make_subplots(rows=1, cols=4)`), fixed `height=460`, and the legend is shown only in the first panel. At phone width the panels compress and the side text runs into the plots.
- Fix options: (a) use a 2×2 grid below a width breakpoint, or (b) keep one row and move the legend and panel titles to a single horizontal legend above the plot. Pick one, then test at 375 px and 1280 px.
- Same review for every figure with `make_subplots` or a right-side legend: `apply_theme` (`libs/portfolio-core/src/portfolio_core/plotting.py`) pushes the legend right by default, and the 360 px per-row minimum (decision 7) applies to `PlotlyFigure.tsx`. Do not change that minimum.

### F6. Mobile flow diagrams are stretched and off-centre
- `apps/showcase-web/src/components/diagrams/FlowDiagram.tsx`: the cylinder icon uses `<svg viewBox="0 0 196 82" preserveAspectRatio="none">` (line ~115). `none` stretches it to fit the node box, which causes the vertical stretch on mobile. Use `xMidYMid meet` (or size the node to the viewBox).
- The off-centre position comes from the zoom and pan logic (`MIN_ZOOM`, `getViewportForBounds`, the phone breakpoint at line ~488). The diagram opens at zoom 1 below the breakpoint, so the centring should be computed from the fitted bounds, not the full canvas width. Verify at 375 px and 390 px.

## 2. Handoff: what Kimi should do (after approval)

Order and gates in section 3. Each item lists its acceptance check.

| # | Item | Files | Acceptance check |
|---|---|---|---|
| H1 | Projects page order: apps, experiments, demos (also in the anchor nav) | `pages/ProjectsIndex.tsx` | Vitest for the render order; desktop and 375 px screenshot |
| H2 | Section title spacing "01 Background" | `components/AppArticle.tsx` and the article section component | Snapshot test; screenshot of both app articles |
| H3 | Section subtitles gray (muted token) in light and dark | the article section stylesheet | Screenshot in both themes |
| H4 | Document-intelligence table through the shared table path | `pages/DocumentIntelligenceArticle.tsx`, `lib/markdown.tsx` | Table has `data-table` and scroll wrapper; no horizontal page scroll at 375 px |
| H5 | Agent-chat summary table from the committed report | `pages/AgentChatArticle.tsx`; build data from `reports/evals-kimi-for-coding.md` | Totals match the report (108/108, 48 executions); table renders |
| H6 | `nab_tune_surface` responsive layout | `projects/03-anomaly-detection/src/anomaly_detection/nab_tune.py` (`tune_figure`); regenerate `reports/figures` via the project's script | No text overlaps at 375 px; `figures` regenerated, not hand-edited |
| H7 | Mobile flow diagrams: no stretch, centred | `components/diagrams/FlowDiagram.tsx` | Screenshot at 375 and 390 px, both themes; existing FlowDiagram tests pass |
| H8 | Reusable figure sizing: list every figure with `make_subplots` or a right legend, and fix only the ones that overlap at 375 px | `libs/portfolio-core/src/portfolio_core/plotting.py` and project figure modules | Screenshot list; no change to the 360 px minimum |

### Gates
After each item:
- `cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps`
- `uv run pytest -q` for any Python item (H6, H8)
- `uv run python scripts/gen_static_registry.py --check` and `scripts/gen_story_short.py --check` if copy or registry changed
- `uv run python scripts/check_headline_numbers.py` if any headline changed

Do not claim a gate passed unless you ran it. Do not run git mutations. Do not deploy. No hosted calls.

## 3. Stop conditions
- A fix needs a change to the 360 px per-row minimum (decision 7): stop and write `OPEN_QUESTIONS.md`.
- A figure change alters a headline number: stop; that needs a separate review.

## 4. Owner decisions (recorded 2026-11-19)
1. H1–H8 approved for Kimi.
2. H6: default applied, 2×2 grid below the breakpoint (option a). Kimi reports the screenshot before and after.
3. F4 agent-chat: default applied, summary table by case kind. Kimi uses totals that match the committed report.

## 5. Per-project quality review (next pass, not started)

The request covers every project's articles, results and performance. A proper pass needs one review file per project, the same template as the 01–13 review. Proposed order: apps first (this pass found issues there), then 03 and 06 (figure and copy issues), then the rest. Each file: copy truth against committed metrics, figure layout at 375 px and 1280 px, and the article's tables. This is the next design after H1–H8 are accepted.
