# ADR-0001: uv workspace monorepo

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Seven showcase projects share contracts, evaluation code, and config discipline.
Options: separate repos (duplication, no platform story), a single flat package
(name collisions, no per-project dependency control), or a uv workspace.

## Decision

Single uv workspace at the repository root with members `libs/*`, `projects/*`,
and `apps/showcase-api`. `apps/agent-chat` and `apps/document-intelligence` are
intentionally isolated uv workspaces so they remain lift-out templates with
their own lockfiles, gates, and container stacks. Shared dependencies (pydantic,
polars, plotly, scikit-learn) are pinned once in each consuming member; heavy
dependencies (torch, transformers, sentence-transformers, faiss) are declared
only by the projects that need them.

## Consequences

- `uv sync --all-packages` gives one coherent environment; `uv.lock` is
  committed and CI installs from it.
- Adding a project = new directory + one line in nothing (glob members) +
  a `pyproject.toml`.
- Cross-imports between projects are discouraged by convention; shared code
  belongs in `libs/`. Current deliberate exceptions are Project 09's declared
  read-only reuse of Project 01's retrieval index and the showcase API's
  runtime serving integrations (Projects 02, 05, and 06).
