# Grade pass 4, Phase 1 (blockers): result

Branch: `wave8-articles-truthfulness-2026-11-25` (switched from `main`; both were at `acf6f9f7`, no conflict).

## Commits

- `2beafb93` fix(portfolio): grade pass 4 phase 1 blockers. Contains the pass 2 content, the axe fix and the CI fence step.
- `5bf660ee` chore(metrics): restamp `_meta` lineage for 01 02 09 11 12. Only five files kept. The payload outside `_meta` is identical for all five.

## Files changed (beyond pass 2)

- `apps/showcase-web/src/lib/markdown.tsx`: table wrapper has `role="region"`, `tabIndex={0}` and `aria-label="Table: <headers>"`.
- `apps/showcase-web/src/components/DataTable.tsx`: new required `ariaLabel` prop and the same attributes. Callers updated: `StoryMetricsTable`, `MetricsTable`, `AgentChatArticle`, `Services`.
- `apps/showcase-web/src/components/FigureCard.tsx`: the data-table wrapper is now named and focusable. A file-level lint disable is used, as in `markdown.tsx`.
- `apps/showcase-web/src/__tests__/markdown.test.tsx`: new case checking that every `.table-scroll` is focusable and named.
- `.github/workflows/ci.yml`: "Diagram fence resolution" step in the gate job.

## Gates (before → after)

Exit 0 before and after:

- ruff, ruff format, mypy
- lint_story_language, check_docs, check_short_copy, check_demo_contract
- gen_static_registry, gen_story_short, gen_route_manifest
- check_headline_numbers, check_diagram_fences, check_figure_axes (3 warnings), check_figure_budget (1 warning)
- lint_ci, mkdocs --strict, git diff --check
- web test (767 → 768 tests), web lint, web build
- pytest: scripts/tests, projects 03/08/09/10/12/13/15, libs/portfolio-core, apps/showcase-api

Changed:

- check_release_artifacts: 1 → 0
- stamp_metrics_meta --check: 1 → 0
- axe (local, 12 routes × 3 viewports × 2 themes): 0 violations in 76 states

Fence gate negative test: renaming one 15 fence id makes the check exit 1. The rename was reverted.

## Experiments, spend, numbers

- Experiments run: none.
- Hosted spend: $0.
- Numbers changed: none.

## Grades

Phase 1 changes no grade axis by itself. It unblocks CI and the redeploy.
