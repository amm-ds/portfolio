# Implementation handoff: figure and diagram sizing

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: draft (not yet approved; Kimi does not start until the owner sets `approved`)
Source design: `collaboration/designs/20261117-figure-review/01-design-brief.md`, `02-architecture-proposal.md`

## Objective

Fix the legibility and empty-space defects in `quality_quant` (08), `family_gap` (06) and `m5_full_sample_series` (02), make diagrams render at fit-to-width by default, and deliver a written inventory of every project visual with a pass or fix verdict.

## Scope

### In scope

- `projects/08-inference-serving/src/inference_serving/figures.py` (`fig_quality_quant` only)
- `projects/06-routing-optimization/src/routing_optimization/figures.py` (`family_gap_figure` only)
- `projects/02-demand-forecasting/src/demand_forecasting/m5_full_figures.py` (`fig_sample_series` only)
- Tests for those three functions: `projects/08-inference-serving/tests/test_figures.py`, and the figure assertions in `projects/06-routing-optimization/tests/test_evaluate.py` and the 02 m5 figure tests
- Regenerated outputs for those three figures only: `reports/figures/quality_quant.html|json`, `reports/figures/family_gap.html|json`, and the 02 m5 payload
- `apps/showcase-web/src/components/diagrams/FlowDiagram.tsx` (canvas cap and initial fit only)
- Existing diagram tests under `apps/showcase-web/src/__tests__/` or next to `components/diagrams/`, only where they assert the old 560px cap (find with `grep -rn "560\|canvasHeight" apps/showcase-web/src`)
- Inventory file: `collaboration/reviews/20261117-figure-inventory.md`

### Out of scope

- Any other figure generator, its output, or its caption/takeaway text
- `PlotlyFigure.tsx` `scaledHeight` (change only if step 2 shows the rule causes the band; otherwise stop and report)
- Any number in copy, metrics JSON, or story YAML
- Hand edits to `staticRegistry.ts`, `route-manifest.json`, or any generated file
- Git mutations (the owner commits)

## Affected surfaces

- 3 Python figure functions and their tests
- 3 regenerated figure outputs and the 02 m5 payload
- `FlowDiagram.tsx` and its tests
- one new file in `collaboration/reviews/`

## Two render surfaces (added after checking production)

- **Showcase UI** (`apps/showcase-web`): renders each figure's Plotly JSON live via `PlotlyFigure.tsx`. Fixes to generators and the diagram canvas reach it after regeneration and build.
- **Production showcase** (`https://alejandromerida.dev/projects/<id>`, the showcase-web app with a live `/projects/<id>/metrics` endpoint): checked 02 on 2026-11-17. The page shows "Metrics could not be loaded. Retry" after a retry too, even though `/projects/02-demand-forecasting/metrics` returns 200 JSON (`git_sha` b2b5b22). No figures render. Root cause found: `getMetrics` in `apps/showcase-web/src/api.ts:96` requires every top-level value to be an object, but the 02 full-panel payload has list and string values. Fix is a separate prerequisite handoff: `collaboration/designs/20261117-metrics-guard-fix/03-implementation-handoff.md`. The m5 figure cannot be verified on prod until that lands and is redeployed.
- **Mkdocs site** (`amm-ds.github.io/portfolio`, GitHub Pages): shows static PNGs from `docs/assets/projects/<id>/`, produced by `scripts/export_readme_figures.py` (`DOCS_FIGURES`). Regenerating the JSON does not change prod. Prod 06 shows `family_gap.png` with the same randomized-dominated scale. Prod 08 shows only `latency_concurrency.png` and `engine_panel.png`; `quality_quant` is not in `DOCS_FIGURES`, so it is not on prod at all.
- Prod is therefore a separate build. Every fixed figure must be re-exported to PNG and committed, or prod stays on the old image.

## Ordered implementation steps

1. **Baseline.** Render `quality_quant.html`, `family_gap.html`, and the 02 m5 figure in the browser at 375px and 1280px. Save screenshots under `$SCRATCH/figure-review/before/`. Confirm or refute the diagnoses in the brief. Record in the inventory file what you saw, including any diagnosis you refute.
2. **Diagnose the empty band.** For each figure, read the authored `height`, subplot domains, and margins from its JSON. Decide whether the band is in the generator (fix there) or in `scaledHeight` (stop and report; do not change the shared rule without a new design). Write the decision in the inventory.
3. **Fix `fig_quality_quant`.** Set explicit cell fill and font colour for the dark surface, and size the table height to its rows so no empty band remains. Keep the PASS/FAIL logic and the takeaway text unchanged.
4. **Fix `family_gap_figure`.** Cap the distance-gap axis so ALNS and OR-Tools bars are readable, and annotate each clipped bar with its true value. Keep the vehicle-delta panel. Remove the empty band below the bottom panel.
5. **Fix `fig_sample_series`.** Use date labels for history and forecast on a single date axis (derive history dates from `cat_meta["forecast_window"][0]` minus 55 to 1 days). Remove the empty tail. Keep the takeaway text unchanged.
6. **Add or update tests.** For each fixed function, assert that the output has the expected trace count, axis type, and that the table or axis range is set. Test behaviour, not the exact HTML.
7. **Regenerate** only the three figure outputs with their scripts, then re-export the PNGs for `family_gap` (06) and the 08 and 02 figures that appear on prod via `uv run python scripts/export_readme_figures.py`. Commit the updated `docs/assets/projects/*` PNGs with the figures. Do not hand edit. Decide with the owner whether `quality_quant` should be added to `DOCS_FIGURES` so prod shows it; do not add it on your own.
8. **Diagram canvas.** In `FlowDiagram.tsx`, make the initial canvas height the fit-to-width height with no 560px cap. Keep `spec.canvasHeight` as an override. Keep the fit control. Confirm the lazy-load path still keeps react-flow out of the entry bundle.
9. **Inventory.** Write `collaboration/reviews/20261117-figure-inventory.md`: one row per report HTML figure (155) and per diagram spec, with columns: project, figure or diagram id, verdict (pass, fix, or needs-owner), and a one-line reason. Verdicts for figures you did not fix are provisional and go to the owner. Do not fix them in this handoff.
10. **Verify.** Re-render the three figures and two diagrams at 375px and 1280px and save screenshots under `$SCRATCH/figure-review/after/`.

## Commands and gates

Run the narrow checks first, then the touched broader gates.

```bash
uv run pytest -q projects/08-inference-serving/tests/test_figures.py
uv run pytest -q projects/06-routing-optimization/tests
uv run pytest -q projects/02-demand-forecasting/tests -k m5
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
uv run python scripts/gen_route_manifest.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_static_registry.py --check
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
```

Regeneration commands for the three figures are the existing project scripts. Kimi names the exact command used in the handoff completion report.

## Data, provider, or deployment constraints

- No paid provider calls. The figures use committed metrics only.
- Figures must trace to committed `reports/metrics.json` or the committed catalog artifacts.
- Mobile layout must stay usable at 375px with no horizontal scroll.

## Acceptance criteria

- [ ] `quality_quant`: text legible on the dark surface; no empty band below the table.
- [ ] `family_gap`: ALNS and OR-Tools bars readable; clipped bars annotated with true values; no empty band below the bottom panel.
- [ ] `m5_full_sample_series`: single date axis; no empty tail.
- [ ] Diagrams open at fit-to-width with no 560px cap on the default view; `canvasHeight` override still works.
- [ ] Inventory file lists all 155 report HTML figures and all diagram specs with a verdict per row.
- [ ] Gates listed above pass, or any failure is reported with its output.
- [ ] Before and after screenshots saved under `$SCRATCH/figure-review/`.
- [ ] Completion report names exact files, commands, and results.

## Known risks

- Changing the diagram default increases page height on long story pages. Check mobile.
- The 02 m5 figure is generated into a payload, not a committed HTML file; its regeneration path may be longer than the others. If it needs a larger change, stop and write `OPEN_QUESTIONS.md` beside this handoff.
- The "wrong" in `quality_quant` may mean more than legibility (see brief, open questions). If Kimi finds a semantics problem, stop and report rather than changing the PASS/FAIL logic.

## Stop conditions

Write `OPEN_QUESTIONS.md` beside this handoff and pause if:

- the empty band comes from `scaledHeight` (step 2);
- the m5 fix needs a change to the payload schema;
- a gate needs external state or paid access;
- the owner's answer to an open question in the brief is needed.
