# Design brief: project visuals review and diagram sizing

Date: 2026-11-17
Designer: Claude Code
Owner: amm-ds (session owner)
Status: draft
Related artifacts: `projects/08-inference-serving/reports/figures/quality_quant.html`, `projects/06-routing-optimization/reports/figures/family_gap.html`, `apps/showcase-web/src/components/diagrams/FlowDiagram.tsx`

## Problem

Three visuals were reported as wrong or badly laid out, and the owner asked for a review of every project visual, with diagrams full size by default.

- `quality_quant` (project 08) is a Plotly table. In the rendered HTML the header and body text are light grey on white cells, so the PASS/FAIL guardrail is close to unreadable. The table also sits in a 300px frame with a large empty dark band below it.
- `family_gap` (project 06) has an empty band at the bottom of the figure. Its top panel is dominated by the `randomized` solver, whose mean gap reaches about 4,800%, so the ALNS and OR-Tools bars that matter sit near zero.
- `m5_full_sample_series` (project 02) shows the same bottom-empty pattern. It is generated in `projects/02-demand-forecasting/src/demand_forecasting/m5_full_figures.py` and served as a payload, not as a committed HTML file.
- Diagrams in the showcase render inside a canvas capped at 560px (`MAX_CANVAS_HEIGHT`), so they open zoomed out and need manual zoom to read. The owner wants them full size by default.

## Context and evidence

| Claim or constraint | Evidence path | Why it matters |
|---|---|---|
| quality_quant table uses default cell colours, light text on white | `projects/08-inference-serving/src/inference_serving/figures.py:115` (`fig_quality_quant`); browser render of the committed HTML | The guardrail is the only pass/fail view of quantization quality; if unreadable it proves nothing for a reader |
| family_gap top panel is scale-dominated by `randomized` | `projects/06-routing-optimization/src/routing_optimization/figures.py:261` (`family_gap_figure`); browser render | Mean gap hides the solvers the story argues for; story copy relies on this figure |
| Diagram canvas capped at 560px, initial fit is not full size | `apps/showcase-web/src/components/diagrams/FlowDiagram.tsx:296-309` | Diagrams open smaller than their content and require zoom |
| Plotly figures scale height to width with per-row min/max | `apps/showcase-web/src/components/PlotlyFigure.tsx:64` (`scaledHeight`) | Explains part of the empty-band symptom; the authored `height` and subplot domains also contribute |
| m5 sample series mixes categorical history labels (`d-55`…`d0`) with date labels on a shared x-axis | `projects/02-demand-forecasting/src/demand_forecasting/m5_full_figures.py:55-135` | Likely cause of the empty tail; not yet confirmed in a browser |
| Public copy for these figures must stay evidence-backed | `docs/engineering/repo-conventions.md` (Truth in copy) | Any caption or takeaway change must trace to committed metrics |

Not yet verified: the m5 figure in the browser at embedded width, and the full inventory of the 155 report HTML figures plus the diagram specs. The handoff makes that inventory the first step.

## Goals and non-goals

Goals:

- Make every figure readable at its embedded width, with no empty bands and no low-contrast text.
- Fix the three named visuals with the smallest change that resolves the defect.
- Make diagrams render at full size by default, with fit-to-width as the initial view.
- Produce a written inventory of every project visual with a verdict per figure, so the owner can prioritise the rest.

Non-goals:

- No new figure types, no new metrics, no change to any committed number.
- No rewrite of the theme system. Fixes go in the shared helper only where the defect is shared.
- No change to generated registry files by hand. They are rebuilt by their scripts.

## Constraints

- Repository conventions and gates: `AGENTS.md` gates. Regenerate `staticRegistry.ts` and `route-manifest.json` only through their scripts, never by hand.
- Compatibility: the HTML and JSON exports under `reports/figures/` are committed; regenerating them changes diffs. Regenerate only figures in scope.
- Privacy and deployment: none beyond the existing repo rules.
- Performance: diagram changes must not pull `react-flow` into the entry bundle (see `LazyFlowDiagram.tsx`).

## Options

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| A. Fix the three figures only, leave diagrams | Smallest change | Diagram complaint unresolved | Owner wants figures first |
| B. Fix the three figures, raise diagram cap and set fit-to-width default | Covers the stated defects with a single diagram change | Diagrams get taller on long pages; must check mobile | Recommended |
| C. Full redesign of all figures under one new theme | Consistent look | Large diff, high regression risk, far beyond the request | Not now |

## Recommendation

Option B. Fix the named figures at their root, correct the diagram canvas default, and deliver a written inventory of the rest. Option B deliberately does not redesign the other figures; those get verdicts in the inventory and become separate, smaller handoffs.

## Acceptance criteria

- [ ] `quality_quant` text is legible on the dark surface and the figure has no empty band below the table.
- [ ] `family_gap` shows the ALNS and OR-Tools bars at a readable scale, and the figure has no empty band below the bottom panel.
- [ ] `m5_full_sample_series` has no empty tail, and the history and forecast share a correct date-based x-axis.
- [ ] Diagrams open at fit-to-width, with no 560px cap on the default view.
- [ ] An inventory file lists all 155 report HTML figures and all diagram specs with pass or fix verdicts.
- [ ] Relevant gates pass (listed in the handoff).

## Rollback and failure behavior

- Failure modes: changed figure heights break the story layout on mobile; the axis change alters the m5 story caption.
- Observability: browser screenshots at 375px and 1280px before and after.
- Rollback path: revert the single commit; generated artifacts regenerate from source.

## Open questions

- Does "wrong" for `quality_quant` mean only legibility, or do the PASS/FAIL semantics also need a change? The current check is "every response met the check", which the figure text already states.
- Should the `randomized` solver be dropped from `family_gap`, shown on a log scale, or kept with an annotation? The recommendation is to keep it, cap the axis, and annotate the clipped bar.
- Is the mobile diagram height acceptable at full size, or should there be a per-diagram `canvasHeight` override (already supported by `spec.canvasHeight`)?
