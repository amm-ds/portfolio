# ADR-0001: uv workspace monorepo

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Seven showcase projects share contracts, evaluation code, and config discipline.
Options: separate repos (duplication, no platform story), a single flat package
(name collisions, no per-project dependency control), or a uv workspace.

## Decision

Single uv workspace at the repository root with members `libs/*`, `projects/*`,
`apps/*`. Shared dependencies (pydantic, polars, plotly, scikit-learn) are pinned
once in each consuming member; heavy dependencies (torch, transformers,
sentence-transformers, faiss) are declared only by the projects that need them.

## Consequences

- `uv sync --all-packages` gives one coherent environment; `uv.lock` is
  committed and CI installs from it.
- Adding a project = new directory + one line in nothing (glob members) +
  a `pyproject.toml`.
- Cross-imports between projects are impossible by convention (projects never
  appear in each other's dependencies); shared code must live in `libs/`.
