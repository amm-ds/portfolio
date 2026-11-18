# Architecture proposal: figure and diagram sizing

Date: 2026-11-17
Designer: Claude Code
Status: draft
Source brief: `01-design-brief.md`

## Scope of the change

Three surfaces, changed in this order:

1. **Figure generators** (Python, per project). Fix the three named figures at source: `fig_quality_quant` (project 08), `family_gap_figure` (project 06), `fig_sample_series` (project 02). Each change is local to its generator and its tests.
2. **Shared Plotly rendering** (`PlotlyFigure.tsx`, `scaledHeight`). Only if the browser check shows the empty band comes from the height rule rather than the authored layout. Default: do not change it.
3. **Diagram canvas** (`FlowDiagram.tsx`). Replace the 560px default cap with fit-to-width as the initial view. Keep `spec.canvasHeight` as an author override, and keep the fit control.

## Why this shape

- Fixing generators at source keeps the committed HTML/JSON as the single truth. The frontend should not compensate for a bad figure.
- The diagram change is the only shared behaviour change. It lives in one component, so one fix covers every diagram in `src/diagrams/`.
- No new abstraction. The existing `apply_theme` helper and `add_takeaway` stay as they are.

## Contracts

- `family_gap_figure(rows) -> go.Figure` keeps its signature. Its output changes: axis range and annotation on clipped bars.
- `fig_quality_quant(run, cfg) -> go.Figure` keeps its signature. Table cell fill and font colour are set explicitly for the dark theme, matching the house table style if one exists. Check for one first (`libs/portfolio-core`).
- `fig_sample_series` keeps its signature. The x-axis uses real dates for history and forecast. The history labels are derived from the same dates, not from `d-55` strings.
- `FlowDiagram` props are unchanged. `DiagramSpec.canvasHeight` keeps its meaning as an override.

## Failure behaviour

- Figure regeneration failures are caught by the existing tests (`test_figures.py`, `test_evaluate.py` figure assertions). A failing test blocks the change.
- Diagram rendering failures already fall back to `DiagramFallback`. No change.

## Observability

- Before and after browser screenshots at 375px and 1280px for each named figure and two diagrams.
- The inventory file records a verdict per figure and per diagram spec.

## Rollback

Revert the commit. Generated artifacts (`reports/figures/*`, `staticRegistry.ts`, `route-manifest.json`) regenerate from source with their scripts, so no manual restore is needed.

## Alternatives rejected

- **Frontend clamp for all Plotly figures**: hides generator defects and changes every figure at once. Rejected.
- **Redesign all figures under a new theme**: large diff, not requested. Rejected for this cycle.
