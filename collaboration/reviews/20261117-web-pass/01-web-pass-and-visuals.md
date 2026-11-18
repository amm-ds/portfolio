# Web pass and visuals review: alejandromerida.dev project pages

Date: 2026-11-17
Reviewer: Claude Code
Scope: production project pages `https://alejandromerida.dev/projects/01-…` to `13-…`, checked in the built-in browser at a 375 px mobile viewport, plus the metrics endpoint for each project.
Status: findings only. No implementation changed.

## Method and limits

- Each page was loaded, waited on, and checked for "could not be loaded" errors and for horizontal page overflow.
- Metrics endpoints were fetched and their top-level value types checked against the frontend guard in `apps/showcase-web/src/api.ts:96`.
- Figures render lazily when scrolled into view. Early checks showed "rendering figure…" placeholders; these are not defects.
- The browser pane could not be restored to a true desktop width, so desktop layout was not checked. Desktop results are not claimed.
- Only one figure (`fig :: family_gap`, project 06) was inspected visually. Other figures were checked for render completion only.

## Summary

| Check | Result |
|---|---|
| Pages load | 13 of 13 load |
| Metrics error box | 3 of 13 fail: 02, 08, 11 |
| Horizontal page overflow at 375 px | None. `scrollWidth` equals the viewport on every page checked |
| Code blocks | Overflow inside their own scroll container; acceptable, not a page overflow |
| Figures render on scroll | Yes, for the figures checked |
| Figure layout at 375 px | Defect in `family_gap` (06); see below |

## Blockers

1. **Metrics guard breaks three project pages (02, 08, 11).** Root cause: `getMetrics` rejects top-level non-object values. Handoff `collaboration/designs/20261117-metrics-guard-fix/03-implementation-handoff.md` now lists all three. Severity: blocker, prod.

## Visual findings

### 06 `fig :: family_gap` at 375 px

- The figure card is about 930 px tall and 335 px wide.
- The plot itself occupies only the left third of the card: panel titles overlap each other, and tick labels are unreadable.
- The legend takes roughly half the width, which squeezes the plot.
- About 200 px of empty space sits below the bottom panel, the "too much empty bottom" symptom from the original report.
- Cause (to confirm in source): the figure is authored at a fixed width with the legend on the right, and `scaledHeight` in `apps/showcase-web/src/components/PlotlyFigure.tsx:64` scales height with width but does not move the legend or shrink the margins at narrow widths.
- Recommended fix (for the figure-review handoff): move the legend below the plot at narrow widths, and reduce the authored height so the card matches the content.

## Other observations (not verified in source)

- The `family_gap` caption says "ALNS averages +1.00 to +6.75 vehicles by family". Check that the range is the per-family mean and not a range over instances. Copy correction if needed.
- Project 08 shows "Metrics could not be loaded", so its quality-guardrail and cost text are not reachable from the page until the metrics fix lands.

## Actions for Kimi (in addition to existing handoffs)

1. Extend the metrics-guard fix to projects 08 and 11 (done in the handoff).
2. Add a mobile legend and height rule to the figure-review handoff: `family_gap` at 375 px must show readable panel titles, a legend below the plot, and no empty band.
3. Re-run this web pass after the metrics fix ships, at 375 px, for 02, 08, and 11.
4. Owner decision: whether a desktop check is needed, since the pane could not be set to a true desktop width here.
