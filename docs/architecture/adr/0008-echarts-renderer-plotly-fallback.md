# ADR-0008: ECharts renderer with per-figure plotly fallback

- **Status:** Accepted; amends ADR-0005 (frontend rendering side)
- **Date:** 2026-11-10

## Context

ADR-0005 made plotly the single visualization library: Python authors every
figure through `portfolio_core.plotting` and the React app rendered the
committed JSON payloads with plotly.js. That contract held, but the renderer
side accumulated problems:

- The plotly.js chunk (~4.8 MB minified) dominated first-visit weight on
  case-study pages, even viewport-gated and split.
- Mobile rendering suffered: touch interactions and resize behavior were the
  recurring complaints in spot checks.
- A second engine was already in the tree for diagrams (React Flow per the
  migration map), so "one renderer" was no longer a real invariant.

## Decision

Keep the ADR-0005 source contract unchanged — every figure payload is still
authored once in Python as themed plotly JSON. Change only the web renderer:

- `apps/showcase-web` converts each committed plotly payload to an Apache
  ECharts option plan (`src/lib/plotlyToECharts.ts`) and renders it with the
  tree-shaken ECharts core (`EChartsFigure`), reusing the shared dark/light
  theme tokens.
- Conversion is gated per figure by a dry run (`supportsECharts`): any
  payload that does not convert cleanly, and any runtime init/conversion
  failure, falls back to the existing `PlotlyFigure` for that figure only.
  The fallback is a rendering detail inside the figure card — a page can
  never break because the pilot engine did.
- plotly.js stays in the bundle as that fallback; ECharts is a lazy-loaded
  chunk.

## Consequences

- Figure authoring, export paths, and the mkdocs/README embedding story are
  untouched — ADR-0005 holds for everything upstream of the web app.
- First-visit chart weight drops and mobile interaction improves; figures
  that need plotly-specific traces keep working through the fallback.
- The conversion layer is a maintained mapping (plotly trace types → ECharts
  series): new figure kinds must either convert or accept the plotly
  fallback rather than extend the converter ad hoc.
