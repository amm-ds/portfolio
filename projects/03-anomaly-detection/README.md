# 03 — Anomaly Detection over Telemetry

Unsupervised anomaly detection evaluated honestly on **real data first**: 12
series from the Numenta Anomaly Benchmark (AWS CloudWatch, traffic sensors,
known-cause system failures) with labelled event windows, plus a seeded
synthetic telemetry stream (CPU, memory, latency) that remains the
clearly-labelled CI / fast path. Three classical detectors compete behind
explicit data-quality gates, with pointwise PR-AUC kept distinct from
event-aware range-F1 and time-ordered train/test splits throughout.

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

## Wave 13: NAB real data becomes the primary track

External-audit driven: real data now headlines, and the metrics lead with what
an audit asks for — events, not points. The seeded synthetic telemetry
generator **stays as the clearly-labelled CI / fast path** (the entire
test-suite runs on it); NAB is the default `data_source` for real runs.

**NAB** ([dataset card](https://amm-ds.github.io/portfolio/data-registry/nab/),
[import manifest](../../docs/data-registry/imports/nab.json)): a bounded subset of 12
series from the [Numenta Anomaly Benchmark](https://github.com/numenta/NAB)
spanning `realAWSCloudwatch`, `realKnownCause`, and `realTraffic`, each
checksum-pinned, with labelled anomaly windows from `combined_windows.json`
(cite Ahmad, Lavin, Purdy & Agha 2017, Neurocomputing).

**Pointwise and event-aware metrics stay distinct** (audit recommendation):
ROC-AUC and PR-AUC rank individual minutes; they are not event metrics. For the
event-aware view, a labelled window counts as detected when at least one alert
falls inside it (lead tolerance 0, documented in `nab.py`), while range recall
additionally weights overlap and range precision penalizes alerts outside any
window. Results on the current snapshot (IsolationForest, train-anchored 2%
alert threshold, 9 of 12 series evaluable — the other 3 have all labelled
windows inside the train split and are excluded from aggregates, not scored as
misses):

| NAB group | pointwise PR-AUC | range-F1 | range prec./rec. | windows touched (alerts emitted) |
|---|---|---|---|---|
| realAWSCloudwatch | 0.404 | 0.088 | 0.049 / 0.500 | 3/3 (132) |
| realKnownCause | 0.438 | 0.074 | 0.040 / 0.938 | 8/9 (1 289) |
| realTraffic | 0.728 | 0.310 | 0.232 / 0.750 | 5/5 (188) |
| **overall** | **0.527** | **0.157** | **0.107 / 0.729** | **16/17 (1 609)** |

The event-window verdict leads: at least one alert touches 16 of 17 labelled
windows, while overlap-weighted range recall is 0.729 and range precision is
0.107. The fixed-threshold run emits 1 609 alerts in total; that is observed
alert load, not the minimum required to detect those windows. Honest
detector-vs-family note: only IsolationForest has been run on NAB so far, so
the benchmark-group results are IsolationForest's alone (strongest on
realTraffic, weakest range recall on realAWSCloudwatch at 0.500); the
cross-detector winner claim exists on the synthetic ladder only — tuned
IsolationForest by ROC-AUC (0.9171), tuned OCSVM by PR-AUC (0.1355), LOF at
chance either way. (NAB ROC-AUC 0.735 overall, reported secondary per the
audit.) The adaptive streaming mode runs on NAB too: its drift trigger fires
on 31 of 120 chunks on real series — the median/IQR trigger calibrated on
synthetic is too twitchy for real score noise, an honest finding for the
tuning backlog.

**The honest delta** — synthetic untuned IsolationForest scores **ROC-AUC
0.9158 / PR-AUC 0.1239**, versus NAB pointwise PR-AUC 0.527 (residual features
later reach 0.9999 ROC-AUC on synthetic). The synthetic track's injected
anomalies are *trivially separable*, so it can demonstrate pipeline mechanics,
HPO behavior, and detector-family failure modes, but it **cannot** rank
solutions on precision at real anomaly rarity. On NAB the champion touches
16/17 windows while emitting 1 609 alerts (range precision 0.107): the real
problem is the false-positive firehose, exactly what the synthetic track could
never show.
Figures: `nab_timelines` (six representative series, true vs. detected
windows), the downsampled single-series `nab_timeline_nyc_taxi` (3 of 4
labelled windows detected, 179 alerts, every 2nd test-window minute),
`nab_score_distribution`, `nab_alert_budget`; artifact `reports/nab_metrics.json`.

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

## Wave 14: NAB detector-family × feature sweep + alert budgets

The roadmap round the NAB track was missing: every detector family and both
feature sets on the real benchmark, plus the alert-load layer (`cli
nab-sweep`, artifact [`reports/nab_sweep.json`](reports/nab_sweep.json)). All
six cells are untuned, share the headline conventions (70/30 time split,
train-anchored 2% threshold, lead 0, mean over all 12 series), and each run
scores three alert streams: **raw** (every above-threshold minute pages),
**deduped** (contiguous runs fire one page at the run's max-score minute),
**budgeted** (deduped pages plus a per-series cap of one page per 24 h).

**No detector family wins NAB.** Pointwise PR-AUC spans 0.515–0.574 across
the grid — best is LOF on rolling+residual features (0.574), IsolationForest
on rolling features alone reaches 0.565, and the headline
IsolationForest+residual recipe sits at 0.527 (bit-identical to the headline
pass: 1,609 raw alerts). Raw range recall is 0.688–0.750 with 1,609–3,586
alerts emitted. Rolling-median residuals — decisive on synthetic (0.9158 →
0.9999 ROC-AUC) — do **not** transfer: the anomaly-blob diagnosis is a
property of the injected data, not of NAB incidents.

**Budgeting the page stream works without retraining.** Dedup + the 24 h
per-series cap cut pages 20–30× and raise range-F1 in *every* cell, because
most raw pages were re-alerts of the same incident minutes:

| sweep cell (raw → budgeted) | alerts | range recall | range-F1 |
|---|---|---|---|
| isolation_forest + rolling | 1,864 → 66 | 0.729 → 0.604 | 0.154 → 0.388 |
| isolation_forest + rolling_residual | 1,609 → 80 | 0.729 → 0.562 | 0.157 → 0.315 |
| lof + rolling | 3,263 → 109 | 0.750 → 0.542 | 0.086 → 0.213 |
| lof + rolling_residual | 3,586 → 122 | 0.750 → 0.542 | 0.088 → 0.200 |
| ocsvm + rolling | 2,412 → 87 | 0.688 → 0.521 | 0.086 → 0.281 |
| ocsvm + rolling_residual | 2,253 → 91 | 0.688 → 0.438 | 0.102 → 0.214 |

The recall cost of the cap is ≈0.13–0.25. The 24 h cooldown is a documented
operating assumption, not a tuned optimum.

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
uv run python -m anomaly_detection.cli nab            # NAB headline track (12 series, event metrics)
uv run python -m anomaly_detection.cli nab-sweep      # detector x feature sweep + alert budgets
# or via DVC:
dvc repro projects/03-anomaly-detection
```

Tests (offline, synthetic fixtures only, ~6 s, 94% package coverage):

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
  contextual features, subspace ensembles) — is where the real work lies.
- **Full reproducibility**: one seed regenerates data, features, models,
  metrics, and figures end-to-end in seconds.

## Roadmap

Delivered so far: Optuna HPO, seeded random baseline, adaptive-threshold
streaming, rolling-median residual features, NSL-KDD transfer probe, the NAB
real-data primary track with event-based metrics — and the wave-14 sweep: all
three detector families × both feature sets on NAB (PR-AUC 0.515–0.574, no
winner; residuals do not transfer their synthetic dominance), plus episode
deduplication and a 24 h per-series page budget that cut alerts 20–30× while
*improving* range-F1 in every cell (headline config 1,609 → 80 pages,
range-F1 0.157 → 0.315, recall 0.729 → 0.562). What remains:

- **Recalibrate the adaptive drift trigger on real data** — the median/IQR
  trigger tuned on synthetic fires on 26% of NAB chunks; it needs a
  higher z threshold or a variance-normalised statistic before production use.
- **Tune the alert-budget operating point** — the 24 h per-series cap is a
  documented assumption; per-family thresholds and cooldowns chosen on
  train-side validation (never against test labels) are the next step.
- **Range precision is still the wall** (0.05–0.12 raw across the sweep) —
  unattended paging stays deferred until real-data precision improves.
