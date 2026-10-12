# 03 — Anomaly Detection over Telemetry

Unsupervised anomaly detection on server-style telemetry (CPU, memory, latency):
three classical detectors compete on a seeded synthetic stream with injected
ground-truth anomalies, evaluated with time-ordered train/test splits behind
explicit data-quality gates.

> **Showcase status:** working showcase on the standard platform (flagship
> projects are `01-rag-agent` and `07-open-data-mobility`). See the
> [Roadmap](#roadmap) for planned deepening.

## Problem

A service-monitoring team wants to flag anomalous telemetry minutes
(CPU/memory/latency) without labeled history. We compare three standard
unsupervised detectors — IsolationForest, Local Outlier Factor (LOF), and
One-Class SVM — on a reproducible telemetry stream with a known 2% anomaly
injection, and we ask: how well does each detector generalize to a later
time window, at a fixed (not tuned) operating threshold?

## Design

Full rationale, the options considered, and the detector-failure analysis:
[DESIGN.md](DESIGN.md). Summary of the pipeline:

1. **prepare** — seeded synthetic telemetry (`portfolio_core.synthetic.telemetry`,
   n=20 000, anomaly_rate=0.02, seed=42), persisted as parquet with a versioned
   `DatasetContract` (checksum, source, license, snapshot date).
2. **validate** — DQ gates as data, not prints: per-column null rate ≤ 1%,
   `cpu`/`mem` within [0, 100], `latency_ms` > 0. Any failure persists
   `reports/dq_report.html` and halts the pipeline loudly (`DQGateError`).
3. **features** — polars ETL: raw signals plus rolling mean/std per signal over
   windows [10, 60]; warm-up rows dropped so the matrix is complete.
4. **train** — IsolationForest, LOF (`novelty=False`, `fit_predict`), and
   One-Class SVM (`nu=contamination`) fit on the first 70% of the timeline only.
5. **evaluate** — detectors scored on the held-out final 30%; ROC-AUC and PR-AUC
   per model; binary flags at a fixed contamination-quantile threshold; HTML
   report + interactive figures (ROC overlay, PR overlay, telemetry with the
   best model's flags vs. ground truth).

## Results (real run: seed 42, n=20 000, test window = 5 983 rows, prevalence 1.89%)

| model | ROC-AUC | PR-AUC |
|---|---|---|
| isolation_forest | **0.9158** | **0.1239** |
| lof | 0.5272 | 0.0195 |
| ocsvm | 0.3368 | 0.0241 |
| random (seeded baseline) | 0.5091 | 0.0194 |

Exact values in [`reports/metrics.json`](reports/metrics.json); the
full evaluation report is [`reports/report.html`](reports/report.html)
with figures in `reports/figures/`:

- `eda_signals_overview.html` / `.json` — first 2 days of raw telemetry with
  injected anomalies marked
- `roc_curves.html` / `.json` — ROC overlay with the random baseline and the
  chance diagonal
- `pr_curves.html` / `.json` — PR overlay with the random baseline and the
  prevalence baseline
- `telemetry_flags.html` / `.json` — test-window telemetry with the best
  model's flags (pink ✗) vs. ground-truth anomalies (amber strip)

**IsolationForest wins decisively**: ROC-AUC 0.9158 vs. 0.5091 for the seeded
random baseline (**+0.41**), and PR-AUC 0.124 vs. the 0.019 prevalence floor
(**6.5×**). LOF and One-Class SVM are at or below the random reference — and
that is the finding, not a bug: the injected anomalies form a compact,
self-similar cluster (mean k-NN distance ≈ 18.9 inside the blob, ≈ 8.5 for
normal points, but *within* the blob spacing is uniform). LOF only compares a
point to its local neighbourhood, so inside the blob every point looks normal
(median LOF ≈ 1.11 on test anomalies, indistinguishable from normals at
≈ 1.09) — its ROC-AUC of 0.527 is not better than coin-flip (0.509). The RBF
One-Class SVM folds the dense blob into its normal region (0.337). Only
IsolationForest — which isolates points by random partitioning — treats "far
away" as "anomalous" regardless of local density.
See DESIGN.md for the full analysis and what we would do about it in
production.

Runtime of the full pipeline on this machine: **~2 s** (well under the 1-minute
budget). All 8 DQ gates pass; the persisted report is
[`reports/dq_report.html`](reports/dq_report.html).

## Reproduce

```bash
# from the repository root
uv run python -m anomaly_detection.cli all          # full pipeline
# or stage by stage (matches dvc.yaml):
uv run python -m anomaly_detection.cli prepare
uv run python -m anomaly_detection.cli validate
uv run python -m anomaly_detection.cli features
uv run python -m anomaly_detection.cli train
uv run python -m anomaly_detection.cli evaluate
# or via DVC:
dvc repro projects/03-anomaly-detection
```

Tests (offline, synthetic fixtures only, ~5.7 s, 95% package coverage):

```bash
uv run pytest projects/03-anomaly-detection -q
```

## What this demonstrates for a client

- **Guardrailed data pipelines**: DQ gates expressed as data (`DQReport`),
  persisted as artifacts, and enforced loudly before any model trains — bad
  data stops the pipeline with evidence, not silent garbage.
- **Leakage-free evaluation**: detectors train on the past only, are scored on
  a future window, and the decision threshold is fixed a priori from an
  assumed contamination — metrics a client can trust, not tuned ones.
- **Honest model comparison**: we report the losers too, with a verified
  mechanism (local-density blindness to clustered anomalies), rather than
  cherry-picking the winner. That diagnosis — and the remedy (residual /
  contextual features, subspace ensembles) — is the senior part of the work.
- **Full reproducibility**: one seed regenerates data, features, models,
  metrics, and figures end-to-end in seconds.

## Roadmap

- **Optuna HPO** for detector hyperparameters (e.g. LOF `n_neighbors`, OCSVM
  `gamma`/`nu`) with the time-ordered split as the objective — cheap here
  because the pipeline runs in ~2 s.
- **Real-data track**: swap the generator for node-exporter / Google Borg /
  Azure VM traces behind the same `DatasetContract`, keeping the synthetic
  fallback for CI.
- **Temporal-residual features** (`x - rolling_median`, seasonality-adjusted
  z-scores) designed specifically to break up self-similar anomaly clusters,
  plus an ensemble vote across detector families.
- **Alert-volume simulation**: cost-aware thresholding (precision at fixed
  alerts/day) instead of a fixed contamination quantile.
