# ADR-0007: DVC beyond pipelines — declarative metrics, experiments, dataset registry

- **Status:** Accepted
- **Date:** 2026-10-15

## Context

ADR-0003 established DVC pipelines for reproducibility. Three capabilities were left
on the table: metrics management (every project writes `reports/metrics.json` but
nothing consumed it declaratively), experiment versioning (HPO studies ran as
one-off scripts with best-params files), and the dataset registry (markdown cards +
custom checksum scripts, but no machine-readable versioned references to the
external sources themselves).

## Decision

Layer the full DVC feature set on top of the existing pipelines:

1. **Metrics**: every project's `dvc.yaml` declares `reports/metrics.json` under its
   evaluate stage's `metrics:` (not `outs:` — a path cannot be both). Metrics are
   DVC-tracked and diffable via the committed `dvc.lock`
   (`dvc metrics show`, `dvc metrics diff`, Makefile `metrics-show`).
2. **Experiments**: parameter-sweep and what-if runs go through
   `dvc exp run --queue --set-param ...` (Makefile `exp-run`/`exp-show`); promising
   experiments are applied/renamed into params.yaml — the HPO stages persist the
   outcome, experiments persist the journey.
3. **Dataset registry**: `registry/` holds one `dvc import-url --no-exec` manifest
   per external dataset — source URL + version metadata without downloading.
   `dvc update registry/` refreshes deliberately; project prepare stages remain the
   fetch path (checksum gates), unchanged.

## Consequences

- `dvc metrics diff` gives per-commit metric regression review — the drift runbook
  gains a one-command check.
- Figures stay with plotly (ADR-0005); DVC plots were considered and skipped — our
  metrics JSON is nested per-run, not tabular, and plotly already serves visuals.
- No cloud remote is assumed; `dvc push` remains optional (ADR-0003 unchanged).
- CI stays DVC-free; metrics/experiments/registry operations are release-time
  verification, documented per project.
