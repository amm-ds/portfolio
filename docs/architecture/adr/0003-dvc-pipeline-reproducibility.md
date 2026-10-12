# ADR-0003: DVC pipelines for reproducibility

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

"Reproducible" must mean something testable: from a clean clone, a stranger
reproduces headline results. Options: ad-hoc scripts (no dependency tracking),
heavy orchestrators (Airflow — overkill for laptop-scale), or DVC.

## Decision

DVC pipelines per project with explicit stages (`prepare → … → evaluate`),
parameters in `params.yaml`, and prepared artifacts tracked by DVC. Raw data is
never committed; dataset cards pin URLs + checksums and `prepare` fails loudly
on mismatch. No cloud remote is assumed — `dvc repro` regenerates everything
locally; a remote is an optional add-on.

## Consequences

- Every stage is a pure function of (params, code version, upstream artifacts).
- CI does not run full `dvc repro` on multi-GB datasets; it runs unit tests and
  synthetic-mode pipeline smoke tests. Real-data reproduction is verified at
  release time and documented per project.
- Stage scripts are thin: they call into typed library/project code, keeping
  business logic testable outside DVC.
