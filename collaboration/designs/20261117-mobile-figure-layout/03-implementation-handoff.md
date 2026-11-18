# Implementation handoff: mobile figure layout (legend and height at narrow widths)

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; the per-row minimum height change stays blocked until the owner decides it separately)
Source review: `collaboration/reviews/20261117-web-pass/01-web-pass-and-visuals.md`

## Objective

At 375 px, the family_gap figure (project 06) must show readable panel titles, a legend below the plot, and no empty band. The fix is in the shared Plotly renderer so it applies to every figure at narrow widths, with the figure generator unchanged.

## Root cause (confirmed in source)

- `libs/portfolio-core/src/portfolio_core/plotting.py:157-158`: `apply_theme` sets the legend to the right (`_LEGEND_RIGHT`) whenever a figure does not position its own legend. `family_gap_figure` does not position its legend, so it gets the right-side legend.
- `apps/showcase-web/src/components/PlotlyFigure.tsx:64-75` (`scaledHeight`): height scales with container width and has a per-row minimum of 360 px per panel. The renderer never changes the legend position or margins, so at 335 px the legend takes about half the plot width.
- The card is about 930 px tall for a 335 px card. That height comes from the two-row minimum (720 px) plus the figure's own caption and margin. Confirm the exact split in the browser before changing the rule.

## Scope

### In scope
- `apps/showcase-web/src/components/PlotlyFigure.tsx` (narrow-width legend placement and margins, applied in the layout builder near line 201-235)
- `apps/showcase-web/src/components/PlotlyFigure.test.tsx` or the existing figure tests under `apps/showcase-web/src/__tests__/` (new narrow-width tests)
- `apps/showcase-web/src/components/FigureCard.tsx` only if the card's minimum height contributes to the empty band (check first)

### Out of scope
- `libs/portfolio-core/src/portfolio_core/plotting.py` (the desktop default stays the same; do not change every generator's legend)
- `projects/06-routing-optimization/src/routing_optimization/figures.py` (figure data and axes stay unchanged; the axis fix is in the figure-review handoff)
- Any regenerated JSON or HTML under `reports/figures/`
- Git mutations

## Ordered steps

1. **Measure first.** In the browser at 375 px, record for `fig :: family_gap`: card height, plot area height, legend bounding box, and bottom empty space. Save the numbers in the completion report. If the empty band comes from `FigureCard` min-height rather than the plot, stop and report before changing anything.
2. **Narrow-width legend.** When the container width is below a single named breakpoint (use 600 px, and name the constant), move a right-side legend to a horizontal legend below the plot (`orientation: "h"`, `y` below the x-axis, `x: 0`). Leave wide layouts unchanged.
3. **Margins.** At the same breakpoint, reduce left and right margins so the plot uses the card width. Keep the title and subtitle.
4. **Height.** Do not change `scaledHeight` constants without measuring. If the 720 px minimum for two rows creates the empty band, propose a lower per-row minimum for narrow widths in the completion report and wait for owner approval before committing it.
5. **Tests.** Add tests for: (a) legend moves to horizontal below the plot below 600 px; (b) legend stays on the right at 1024 px; (c) a figure with a legend already positioned by the generator keeps its position at narrow widths.
6. **Verify in browser.** Re-check `fig :: family_gap` on prod-equivalent local dev at 375 px and at 1024 px. Save before and after screenshots.

## Owner decision required

- **Per-row minimum height at narrow widths.** Changing the 360 px per-row minimum affects every multi-panel figure. Do not change it without owner approval (step 4).

## Commands and gates

```bash
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
```

Run the local API and web dev server to check the page (`uv run uvicorn showcase_api.main:app --port 8000` in `apps/showcase-api`, then `npm run dev` in `apps/showcase-web`). The page needs the metrics guard fix to show metrics for 02, 08 and 11; 06 is not affected by that fix.

## Acceptance criteria

- [ ] At 375 px, the family_gap legend sits below the plot and panel titles do not overlap.
- [ ] At 1024 px, layout is unchanged from before (verified by before and after screenshots).
- [ ] Narrow-width tests pass; a deliberately broken breakpoint makes them fail.
- [ ] Measured numbers (card height, plot height, empty band) are in the completion report.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause before changing the per-row height minimum. Pause if the empty band comes from `FigureCard` and needs a card-level change.
