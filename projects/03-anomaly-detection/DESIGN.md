# DESIGN — 03 Anomaly Detection over Telemetry

## Requirements

- Detect anomalous minutes in synthetic telemetry (cpu, mem, latency_ms) with
  unsupervised detectors; ground-truth `is_anomaly` used for evaluation only.
- Data-quality gates must halt the pipeline loudly on violation and persist a
  human-readable report.
- Detectors train on the train window only; scoring on the test window uses a
  fixed contamination (no threshold tuning against ground truth).
- Per-model ROC-AUC + PR-AUC with overlay figures and a telemetry view marking
  the best model's flags.
- Runtime < 1 min; fully seeded and reproducible; tests run offline.

## Options considered

### Data

| option | decision |
|---|---|
| Real telemetry (node-exporter / cloud VM traces) | Rejected for now: needs network download and brittle licensing; kept as roadmap item behind the same `DatasetContract`. |
| Seeded synthetic generator from `portfolio_core.synthetic` | **Chosen**: offline, deterministic, ground-truth labels for evaluation, shared platform fallback. |

### Features

| option | decision |
|---|---|
| Raw signals only | Rejected: seasonal sinusoids bury contextual shifts. |
| Raw + rolling mean/std over windows [10, 60] (polars `rolling_mean`/`rolling_std`, `min_samples=window`) | **Chosen** — spec-compliant, complete-case matrix after dropping warm-up rows. |
| Residuals / seasonality-adjusted z-scores | Roadmap: the current injection produces self-similar anomaly clusters that rolling aggregates cannot break up (see below). |

### Detectors

| option | decision |
|---|---|
| IsolationForest | **Chosen**: partition-based; "far away ⇒ anomalous" regardless of local density. |
| LOF (`novelty=False`, `fit_predict` on train) | **Chosen** (per spec). Test-window scoring replicates `score_samples` math on the fitted neighborhood, because sklearn ≥ 1.9 blocks `score_samples`/`decision_function` when `novelty=False`. |
| One-Class SVM (`nu=contamination`, RBF) | **Chosen**: classic boundary-based baseline. |
| Autoencoder / deep model | Rejected: overkill for a 2%-contamination tabular problem and for a <1-min runtime budget. |

### Threshold

Fixed `1 − contamination` quantile of the test scores, per model. Chosen over
tuning a threshold on ground truth to keep the evaluation honest (no label
leakage into the operating point).

## Pipeline

```mermaid
flowchart LR
    A[prepare<br/>seeded synthetic telemetry<br/>+ DatasetContract] --> B[validate<br/>DQ gates → DQReport<br/>reports/dq_report.html]
    B -->|raise_if_failed| C[features<br/>raw + rolling mean/std<br/>windows 10, 60]
    C --> D[train<br/>IF / LOF / OCSVM<br/>train window 70%]
    D --> E[evaluate<br/>ROC-AUC, PR-AUC<br/>fixed contamination threshold]
    E --> F[reports<br/>metrics.json + report.html<br/>figures html+json]
```

## Finding: why LOF and OCSVM fail here

The injected anomalies (cpu += U(30, 50), latency ×= U(2, 5), independent of
the seasonal phase) form a **compact, self-similar cluster** in feature space.
Verified on the train window (k=20 nearest-neighbor distance, euclidean):

| group | mean k-NN distance |
|---|---|
| anomaly | 18.9 |
| normal | 8.5 |

- **LOF is purely local**: it compares a point's density only to its
  neighbors' density. Inside the blob, spacing is uniform, so every anomaly's
  LOF ≈ 1 (median test score on anomalies: 1.11 vs. 1.09 on normals). LOF
  never "looks outward" at the bulk of normal data, so isolation from normals
  does not register. Test ROC-AUC 0.527, PR-AUC 0.019 (below the 0.019→0.02
  prevalence band).
- **One-Class SVM (RBF) models the support of normal data**, and the dense
  blob is far more kernel-dense than the thin seasonal trajectory the normals
  trace, so the blob lands inside the learned boundary. Test ROC-AUC 0.337.
- **IsolationForest isolates by random partitioning**: a point in a distant
  blob gets isolated in a handful of splits no matter how dense the blob is.
  Untuned test ROC-AUC is 0.9158, but PR-AUC is only 0.1239; these are distinct
  pointwise ranking metrics, and the later tuned OCSVM leads PR-AUC.

Production remedies (roadmap): residual features against a rolling median to
de-cluster anomalies, subspace ensembles, and cost-aware thresholds.

Note: scaling was evaluated and rejected — it did not fix the local-density
blindness (LOF 0.63 at best with k=100 + standardization vs. 0.53 raw) and
adds a fitted-transformer artifact; keeping raw features preserves the
cleanest, most auditable story.

## Changelog

- 0.7.0 (2026-10-30): wave-15 operating-point tuning (`nab-tune`, artifact
  `reports/nab_tune.json`, figure `nab_tune_surface`): the (threshold budget,
  per-series cooldown) operating point is selected per detector family on
  train-side validation only — inner 80/20 split of each series' train window
  (fit on 80%, validate on the last 20%, mirroring the HPO slice), budgeted
  alert stream scored on the 6 labelled windows overlapping the validation
  slices (5 of 12 series), mean over 12 series × 2 feature sets; budgets
  0.5–8% × cooldowns 6–72 h, conservative adoption (argmax ties → fewer pages
  → default → simpler point; ≥0.05 validation range-F1 margin over the
  documented (2%, 24 h) default). One test pass per family through the
  unmodified sweep machinery (`evaluate_sweep_series` gained optional
  `threshold_budget`/`cooldown_hours` overrides; sweep numbers unchanged,
  regenerated bit-identically). Measured verdict: IsolationForest adopts
  (0.5%, 24 h) and transfers (budgeted 66 → 33 / 80 → 46 pages, range-F1
  0.388 → 0.433 / 0.315 → 0.382); LOF keeps the default (flat surface, best
  gain +0.042); OCSVM's marginal adoption (0.5%, 72 h, +0.056) fails to
  transfer on test (−0.043/+0.033 F1) — published as the measured limit of
  6-window validation evidence. New tests pin the split bounds, the
  test-row exclusion, grid monotonicity, the adoption/tie-break rules, and
  the offline stage.
- 0.6.0 (2026-10-29): wave-14 roadmap sweep (`nab-sweep`, artifact
  `reports/nab_sweep.json`): 12 series × 3 detectors (isolation_forest / lof /
  ocsvm, untuned) × 2 feature sets (rolling vs rolling+residual), all under
  the headline conventions (train-anchored 2% threshold, lead 0, mean over all
  12 series). Headline IsolationForest+residual reproduces bit-identically
  (1,609 alerts, PR-AUC 0.527). No family wins: PR-AUC 0.515–0.574; residuals
  do not transfer their synthetic dominance. Alert-load layer on every run:
  episode dedup (contiguous runs fire one page at the max-score minute) plus a
  per-series 24 h page budget — pages drop 20–30× and range-F1 improves in
  every cell (headline 1,609 → 80 pages, F1 0.157 → 0.315, recall
  0.729 → 0.562). New tests pin the dedup/budget math.
- 0.5.0 (2026-10-15): wave-13 external audit — NAB real data becomes the
  primary track (`data_source="nab"` default; synthetic generator stays the
  labelled CI/fast path): 12 checksum-pinned series across
  realAWSCloudwatch/realKnownCause/realTraffic with pointwise ROC-AUC/PR-AUC
  kept distinct from event-aware range precision/recall/F1 (window detected
  if >=1 alert inside, lead tolerance 0; range recall also weights overlap).
  Headline: overall pointwise PR-AUC 0.527 / range-F1 0.157 (16/17 windows
  touched, 1609 alerts emitted, range precision 0.107). Synthetic untuned
  IsolationForest instead scores ROC-AUC 0.9158 / PR-AUC 0.1239: the injected
  anomalies are trivially separable, so the synthetic track cannot expose the
  real-data false-positive firehose. New figures `nab_timelines`,
  `nab_score_distribution`, `nab_alert_budget`; adaptive streaming runs on
  NAB (drift trigger fires on 31/120 chunks — recalibration remaining);
  series without evaluable test windows are excluded from aggregates, never
  scored as misses. Dataset card `docs/data-registry/nab.md` + import
  manifest `data-registry/imports/nab.json`.
- 0.4.0 (2026-10-13): wave-7 roadmap implementation — adaptive-threshold
  streaming simulation (`detect --adaptive`: 5 × 1 440-row chunks, median/IQR
  drift z, 0 events on the stable test stream, fixed 120 flags @ 15.9%/15.0%
  recall/precision vs. adaptive 113 @ 15.0%/15.0%); rolling-median residual
  features (IsolationForest ROC-AUC 0.9158 → 0.9999, PR-AUC → 0.9960;
  anomaly k-distance 20.5 → 59.9 vs. normal 9.5 → 17.0 — blob de-clustered);
  NSL-KDD production track (checksum-pinned mirrors of KDDTrain+/KDDTest+;
  41 mapped features; IsolationForest transfer probe ROC-AUC 0.8817 /
  PR-AUC 0.8916 at 56.9% test prevalence).
- 0.3.0 (2026-10-12): per-family Optuna HPO (`tune` stage: ~30 seeded TPE
  trials, median pruning, validation = last 20% of the train window) with
  tuned detectors persisted to `data/models_tuned/` alongside per-study
  JSON artifacts (best params, importances, trial history). New figures:
  `score_distribution` (normal vs. anomaly score histograms, log y),
  `threshold_sweep` (precision/recall vs. alert budget), `hpo_importance`;
  ROC/PR overlays restyled with `plotting.style_runs`. Real results: tuned
  OCSVM rescued (0.337 → 0.906 ROC-AUC / 0.136 PR-AUC via gamma=0.013),
  IF already near-optimal (+0.001), LOF not rescued (0.527 → 0.505).
- 0.2.0 (2026-10-12): seeded random baseline (uniform scores, `config.seed`)
  added to every evaluation — ROC-AUC 0.5091 / PR-AUC 0.0194 on the real run —
  plotted as an explicit curve in the ROC/PR overlays; `eda_signals_overview`
  figure (first 2 880 minutes of raw telemetry with injected anomalies marked);
  evaluation artifacts moved to the platform-canonical `reports/metrics.json` /
  `reports/report.html`; `story.yaml` case study authored (8 canonical
  sections).
- 0.1.0 (2026-10-12): initial pipeline — prepare/validate/features/train/
  evaluate CLI, DQ gates (null-rate, range, positivity), rolling features
  [10, 60], IF/LOF/OCSVM comparison at fixed contamination, figures +
  metrics.json + report.html. Real results: IF 0.9158/0.1239, LOF 0.5272/
  0.0195, OCSVM 0.3368/0.0241 (ROC-AUC/PR-AUC, seed 42, n=20000).
