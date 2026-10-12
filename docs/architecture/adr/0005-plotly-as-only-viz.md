# ADR-0005: plotly as the only visualization library

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Figures appear in three places: project READMEs/docs (embedded HTML), the
mkdocs site, and the React showcase app. Mixed libraries would mean three
export paths and inconsistent theming.

## Decision

All figures are plotly, built through `portfolio_core.plotting` (shared theme,
consistent sizing, accessible palette). Export paths:

- `fig.write_html(..., include_plotlyjs="cdn")` for docs/README embedding;
- `fig.to_json()` payloads served by the FastAPI showcase API and rendered by
  the React app with plotly.js — one source of truth, interactive in the browser.

## Consequences

- No Streamlit, no matplotlib state machine, no per-project styling drift.
- The shared theme is a branding decision: an evaluator sees one coherent
  visual identity across all seven projects.
- plotly.js is the single frontend chart dependency (bundled once in
  `showcase-web`).
