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
5. **tune** — per-family Optuna HPO (~30 seeded TPE trials, median pruning)
   maximizing validation PR-AUC on the last 20% of the train window; tuned
   detectors refit on the full train window (test window untouched).
6. **evaluate** — untuned + tuned detectors scored on the held-out final 30%;
   ROC-AUC and PR-AUC per run plus a seeded random baseline; binary flags at a
   fixed contamination-quantile threshold; HTML report + interactive figures
   (ROC/PR overlays, telemetry flags, score distributions, threshold sweep,
   HPO importance).

## Results (real run: seed 42, n=20 000, test window = 5 983 rows, prevalence 1.89%)

Run ladder — every row is one scoring run on the same held-out window, at the
same fixed 2% alert budget. Detectors were tuned (30 seeded Optuna trials, TPE
+ median pruning) on a validation slice of the *train* window only.

| run | ROC-AUC | PR-AUC |
|---|---|---|
| random (seeded baseline) | 0.5091 | 0.0194 |
| lof (untuned) | 0.5272 | 0.0195 |
| ocsvm (untuned) | 0.3368 | 0.0241 |
| lof_tuned | 0.5054 | 0.0254 |
| ocsvm_tuned | 0.9056 | **0.1355** |
| isolation_forest (untuned) | 0.9158 | 0.1239 |
| isolation_forest_tuned | **0.9171** | 0.1208 |

**Honest winner:** by ROC-AUC, `isolation_forest_tuned` (0.9171); by PR-AUC —
the metric that matters at 1.9% prevalence — `ocsvm_tuned` (0.1355). Deltas for
the PR-AUC champion: **+0.40 ROC-AUC vs. random** (0.9056 vs. 0.5091) and
**+0.57 vs. its own untuned version** (0.3368 → 0.9056). IsolationForest was
already near-optimal untuned (tuning: +0.001 ROC-AUC).

Key findings:

- **Tuning rescued One-Class SVM.** The wave-1/2 default `gamma="scale"`
  failed (0.337); HPO found `gamma=0.013` (param importance 0.99 — a ~6×
  tighter kernel): tight boundaries carve the anomaly blob out instead of
  folding it in. A detector family that looks hopeless by default can be the
  strongest after honest search.
- **Tuning did not rescue LOF.** Best `n_neighbors` saturated at the search
  cap (200) and test ROC-AUC went *down* (0.527 → 0.505). The failure is
  structural: LOF compares each point only to its local neighbourhood, so
  inside a self-similar anomaly cluster every point looks normal (median LOF
  ≈ 1.11 on test anomalies vs ≈ 1.09 on normals). No neighbourhood size fixes
  a method that never looks outward.
- **At the fixed 2% alert budget the top three detectors tie operationally**:
  each flags 120 test minutes with ~15% recall / ~14% precision. AUC/PR-AUC
  measure ranking quality; the operating point is where an alerting budget
  lives or dies.

Exact values in [`reports/metrics.json`](reports/metrics.json); the
full evaluation report is [`reports/report.html`](reports/report.html)
with figures in `reports/figures/`:

- `eda_signals_overview.html` / `.json` — first 2 days of raw telemetry with
  injected anomalies marked
- `roc_curves.html` / `.json` — ROC overlay (random greyed, champion accented)
- `pr_curves.html` / `.json` — PR overlay with prevalence baseline
- `telemetry_flags.html` / `.json` — test-window telemetry with the best
  model's flags (pink ✗) vs. ground-truth anomalies (amber strip)
- `score_distribution.html` / `.json` — champion score histograms, normal vs.
  anomaly, log-scale y (the most explanatory anomaly figure we have)
- `threshold_sweep.html` / `.json` — champion precision/recall vs. alert
  budget, with the fixed 2% operating point marked
- `hpo_importance.html` / `.json` — parameter importance + trial history for
  the champion family

See DESIGN.md for the full analysis (including why feature scaling was
evaluated and rejected) and what we would do about it in production.

Runtime of the full pipeline on this machine: **~80 s** including 90 HPO
trials, the streaming simulation, the residual probe, and the NSL-KDD
download + transfer probe. All 8 DQ gates pass; the persisted report is
[`reports/dq_report.html`](reports/dq_report.html).

## Wave-7 additions: streaming, residuals, real data

Three roadmap items from earlier waves are now delivered, with real numbers.

**Adaptive-threshold streaming** (`detect --adaptive`, artifact
[`reports/detect.json`](reports/detect.json), figure `adaptive_stream`).
The champion (`isolation_forest_tuned`) scores the test window as a simulated
stream of 5 × 1 440-minute (24 h) chunks. Drift is monitored per chunk with a
robust statistic — the chunk-median shift in units of the train-window score
IQR; when it exceeds `drift_z = 1.0` the threshold is re-anchored to the
drifting chunk's 2% quantile to hold the alert budget:

- Measured per-chunk drift z: 0.027–0.089 — far under the 1.0 trigger, so
  **0 drift events** and the threshold never moved on this stable stream.
- Fixed threshold (test-quantile, wave-2 convention): 120 flags, recall
  15.9%, precision 15.0%. Adaptive (train-anchored threshold): 113 flags,
  recall 15.0%, precision 15.0% — on a non-drifting stream the two agree,
  which is exactly what should happen.

**Rolling-median residual features** (artifact
[`reports/residual_probe.json`](reports/residual_probe.json)). The wave-3
hypothesis — residuals would de-cluster the self-similar anomaly blob — is
**confirmed decisively**: IsolationForest ROC-AUC goes **0.9158 → 0.9999**
(PR-AUC 0.1239 → 0.9960) when six `signal − rolling_median` columns are added.
Why: a rolling median over a 10–60 min window barely moves at an isolated
anomaly minute, so the residual ≈ the full spike magnitude, while normal
minutes keep small residuals — the k-NN evidence shows anomaly k-distance
jumping 20.5 → 59.9 against normal 9.5 → 17.0. Residuals are the right
default feature for this failure mode.

**NSL-KDD production track** (artifacts `data/nsl/` + [`reports/nsl_probe.json`](reports/nsl_probe.json)).
The official UNB page no longer serves the files, so checksum-pinned mirrors
of KDDTrain+.TXT / KDDTest+.TXT are fetched via `portfolio_core.io.fetch`
(43 columns → 41 mapped features, categoricals factorized) behind the same
`DatasetContract`. The champion family (IsolationForest) fits the labeled
125 973-row train split and scores the 22 544-row test split:
**ROC-AUC 0.8817, PR-AUC 0.8916** at 56.9% test prevalence. Honest caveats:
labeled transfer probe (not a leaderboard), unseen attack categories in test,
flow statistics rather than telemetry semantics, ~57% prevalence vs. the 2%
operating point, factorized (not one-hot) categoricals.

## Reproduce

```bash
# from the repository root
uv run python -m anomaly_detection.cli all          # full pipeline
# or stage by stage (matches dvc.yaml):
uv run python -m anomaly_detection.cli prepare
uv run python -m anomaly_detection.cli validate
uv run python -m anomaly_detection.cli features
uv run python -m anomaly_detection.cli train
uv run python -m anomaly_detection.cli tune
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

Delivered so far: Optuna HPO, seeded random baseline, adaptive-threshold
streaming simulation, rolling-median residual features (0.9999 ROC-AUC), and
the NSL-KDD transfer probe. What remains:

- **Make residuals the default feature set** for this failure mode and
  re-run the full run ladder (LOF/OCSVM included) on residual features.
- **Streaming ingest**: replace the chunked simulation with a real
  event source (e.g. message-queue or file-tail) so `detect --adaptive`
  runs against live-shaped traffic with true distribution drift.
- **NSL-KDD hardening**: one-hot categorical encoding, per-attack-category
  breakdown, and comparison against the labeled train split under the
  protocol the benchmark literature uses.
