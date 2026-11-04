# 03 — Anomaly Detection over Telemetry

Unsupervised anomaly detection evaluated honestly on **real data first**: 12
series from the Numenta Anomaly Benchmark (AWS CloudWatch, traffic sensors,
known-cause system failures) with labelled event windows, plus a seeded
synthetic telemetry stream (CPU, memory, latency) that remains the
clearly-labelled CI / fast path. Three classical detectors — and, on the
real-data sweep, a rank-average ensemble of the three — compete behind
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
**ROC-AUC 0.8877, PR-AUC 0.8979** at 56.9% test prevalence. Honest caveats:
labeled transfer probe (not a leaderboard), unseen attack categories in test,
flow statistics rather than telemetry semantics, ~57% prevalence vs. the 2%
operating point, factorized (not one-hot) categoricals — now by a
deterministic lexicographic dense rank (the old appearance-order
`Categorical` codes wandered between runs through the polars string cache, so
the probe only became byte-reproducible after that fix).

## Wave 14: NAB detector-family × feature sweep + alert budgets

The roadmap round the NAB track was missing: every detector family and both
feature sets on the real benchmark, plus the alert-load layer (`cli
nab-sweep`, artifact [`reports/nab_sweep.json`](reports/nab_sweep.json)). All
six cells are untuned, share the headline conventions (70/30 time split,
train-anchored 2% threshold, lead 0, mean over all 12 series), and each run
scores three alert streams: **raw** (every above-threshold minute pages),
**deduped** (contiguous runs fire one page at the run's max-score minute),
**budgeted** (deduped pages plus a per-series cap of one page per 24 h).

**No single detector family wins NAB.** Pointwise PR-AUC spans 0.515–0.574 across
the grid — best is LOF on rolling+residual features (0.574), IsolationForest
on rolling features alone reaches 0.565, and the headline
IsolationForest+residual recipe sits at 0.527 (bit-identical to the headline
pass: 1,609 raw alerts). Raw range recall is 0.688–0.750 with 1,609–3,586
alerts emitted. Rolling-median residuals — decisive on synthetic (0.9158 →
0.9999 ROC-AUC) — do **not** transfer: the anomaly-blob diagnosis is a
property of the injected data, not of NAB incidents. (The wave-16
rank-average ensemble of these families wins the grid — see below.)

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

## Wave 15: train-side operating-point tuning (`nab-tune`)

The roadmap item the sweep left open: tune the (threshold budget, per-series
cooldown) operating point **per detector family on train-side validation only**,
then evaluate once on NAB (artifact
[`reports/nab_tune.json`](reports/nab_tune.json), figure `nab_tune_surface`).
The protocol (`src/anomaly_detection/nab_tune.py`):

1. **Selection surface — no test data.** Each series' train window is split
   80/20 (fit on the first 80%, validate on the last 20% — the same convention
   as the synthetic HPO). Candidate budgets flag that fraction of the
   *fit-slice* scores; the budgeted alert stream is scored with the headline
   event metrics on the 6 labelled windows overlapping the validation slices
   (5 of 12 series), aggregated as the mean over all 12 series × both feature
   sets (24 runs per grid point; budgets 0.5–8%, cooldowns 6–72 h).
2. **Conservative adoption.** The grid argmax (ties → fewer pages → the
   default → simpler point) is adopted only when it beats the documented
   (2%, 24 h) default by ≥ 0.05 validation range-F1; otherwise the default
   stands and the item closes with a measured "no robust gain".
3. **One test pass.** Each family is refit on the full train window and scored
   once on the test window at its adopted point, through the unmodified sweep
   machinery; the comparison table below is read from the committed
   `reports/nab_sweep.json` (same conventions, default operating point).

| family | adopted point | validation F1 (vs default) | test verdict (budgeted stream) |
|---|---|---|---|
| isolation_forest | (0.5%, 24 h) | 0.318 vs 0.237 (+0.081) | **transfers**: 66 → 33 and 80 → 46 pages, range-F1 0.388 → 0.433 / 0.315 → 0.382 (recall −0.08/−0.10) |
| lof | default kept | best gain +0.042 (< margin) | unchanged, as designed |
| ocsvm | (0.5%, 72 h) | 0.206 vs 0.150 (+0.056) | **fails to transfer**: range-F1 −0.043 / +0.033 across its two cells |

The measured takeaway: the tuned IsolationForest operating point is a real,
protocol-driven improvement (half the pages, better range-F1); sub-0.1
validation gains on 6 windows are noise-shaped — OCSVM's adopted point sits on
a fragile peak (grid neighbours average 0.168 against its 0.206) that the test
pass punishes in one cell and barely rewards in the other. The 24 h cap is now
validated for LOF/OCSVM rather than assumed, and the default remains the
published operating point for both. Selection saw only rows and windows left
of the 70% train split; the test window was scored exactly once per family.

## Wave 16: rank-average ensemble + a reproducibility fix

The model/architecture round the roadmap reserved for "subspace ensembles":
the NAB sweep gains a fourth family, **`ensemble`** (`nab_sweep.fit_detector`),
which fits the three base families on the same train slice and scores every
minute by the mean of its normalized ranks under IsolationForest, LOF, and
OCSVM (stable rank ties, no member recalibration). The evaluation contract is
untouched — same 70/30 past-only split, same train-anchored thresholds, same
event-aware metrics, one test pass per family through the unmodified sweep
machinery (`nab_tune` selects its operating point on train-side validation
like any other family).

**The ensemble wins the grid at the frozen default operating point (2%, 24 h):**

| sweep cell (raw → budgeted) | alerts | range recall | range-F1 |
|---|---|---|---|
| ensemble + rolling | 1,157 → 35 | 0.729 → 0.604 | 0.485 → 0.533 |
| ensemble + rolling_residual | 1,003 → 45 | 0.729 → 0.562 | 0.316 → 0.365 |
| (reference) isolation_forest + rolling | 1,864 → 66 | 0.729 → 0.604 | 0.154 → 0.388 |
| (reference) isolation_forest + rolling_residual | 1,609 → 80 | 0.729 → 0.562 | 0.157 → 0.315 |

Against the best tuned single family (IsolationForest at its adopted
(0.5%, 24 h): 33 pages at range-F1 0.433, recall 0.500), the untuned ensemble
at the documented default posts 35 pages at range-F1 0.533 with recall 0.604 —
fewer pages than the tuned single family, better F1, higher recall, and no
tuning step at all. Budgeted range precision on the rolling cell more than
halves the miss rate (0.553 vs IsolationForest's 0.347). Its selection
surface is dead flat (best gain +0.010 at (1%, 12 h), far under the 0.05
adoption bar), so the conservative protocol keeps the default — the winning
candidate needs no operating-point search. Pre-existing sweep/tune cells
reproduce bit-identically; the headline `nab` pass stays IsolationForest for
convention continuity. A per-column median/MAD robust-z statistical family
was measured as an additional candidate and rejected: it never beats the
ensemble cell-for-cell (0.378–0.438 budgeted range-F1 at 70–50 pages).

Also in this round: the NSL-KDD categorical factorization became
deterministic (lexicographic dense rank — appearance-order categorical codes
wandered between runs), making every artifact byte-reproducible end-to-end;
the probe's pinned numbers move 0.8817 / 0.8916 → 0.8877 / 0.8979.

## Wave 17: detector-layer refinement ablation at the fixed budget (`nab-refine`)

The roadmap round for "range precision is still the wall": three refinements
of the detector layer, each ablated against the committed headline recipe on
the identical protocol and windows (12 series, `rolling_residual` features,
70/30 past-only split, train-anchored 2% budget, lead 0, raw/deduped/budgeted
streams — `cli nab-refine`, artifact
[`reports/nab_refinement.json`](reports/nab_refinement.json)):

1. **Calibrated thresholding** — conformal p-values of each score against the
   non-anomalous train scores of its own hour-of-week context (train minutes
   inside labelled windows excluded; thin/absent contexts fall back to the
   series-global set, then to the committed raw cut), with the threshold at
   the budget quantile of the pooled calibration p-values instead of the raw
   score quantile.
2. **Rank fusion** — mean of per-window normalized ranks under IsolationForest
   and LOF, same budget rule applied to the fused reference scores.
3. **Context normalization** — z-normalize each fusion member within its
   hour-of-week context (train statistics) before ranking.

Adoption gate: a candidate is adopted only if precision at the 2% budget and
event range-F1 both improve over the in-artifact baseline while windows
touched holds at 16/17. Measured verdict — **no candidate clears the gate;
the committed detector stands**:

| candidate | alerts (raw → budgeted) | precision@budget | range-F1 | windows touched | PR-AUC |
|---|---|---|---|---|---|
| isolation_forest (committed baseline) | 1,609 → 80 | 0.512 | 0.157 | 16/17 | 0.527 |
| if_calibrated | 2,546 → 103 | 0.490 | 0.148 | 16/17 | 0.522 |
| fusion_if_lof | 786 → 41 | 0.650 | 0.403 | 14/17 | 0.587 |
| fusion_if_lof_norm | 887 → 52 | 0.637 | 0.391 | 15/17 | 0.573 |

- **Calibration spends the budget before scoring.** On the 5-minute series an
  hour-of-week context holds ~40 non-anomalous train minutes, so the conformal
  grid bottoms out at p = 2/(n+1) ≈ 0.049 and the pooled budget quantile lands
  on that grid point (nyc_taxi τ = 0.0488); per-context cuts then hand every
  context its own slice — 2,546 alerts at the 2% face budget, precision and
  range-F1 both down. Post-drift regimes overshoot further
  (machine_temperature_system_failure: 538 → 1,236 alerts).
- **Fusion wins the metrics but loses incidents.** Rank fusion lifts
  precision@budget to 0.650 and range-F1 to 0.403 while cutting raw alerts
  51% — but coverage drops to 14/17, losing one window each on
  machine_temperature_system_failure and speed_7578. Under a gate that prices
  incident coverage first, that trade is not adoptable for a monitoring
  artifact; the normalization variant recovers one window and is otherwise
  dominated, so it fails the same way.
- **The negative result is the deliverable.** The refinement layer is
  measured, gated, and published as such; the page-layer ensemble (wave 16)
  remains the cheapest load cut, and the drift-trigger recalibration stays the
  open item.

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
uv run python -m anomaly_detection.cli nab-tune       # train-side operating-point selection + one test pass
uv run python -m anomaly_detection.cli nab-refine     # detector-layer refinement ablation + adoption gate
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
  cherry-picking the winner. That diagnosis produced the remedy it promised:
  the rank-average ensemble of the three families wins the real-data sweep at
  the frozen default — while the residual-feature fix, huge on synthetic,
  honestly failed to transfer and is published as such.
- **Full reproducibility**: one seed regenerates data, features, models,
  metrics, and figures end-to-end in seconds.

## Roadmap

Delivered so far: Optuna HPO, seeded random baseline, adaptive-threshold
streaming, rolling-median residual features, NSL-KDD transfer probe, the NAB
real-data primary track with event-based metrics — the wave-14 sweep: all
three detector families × both feature sets on NAB (PR-AUC 0.515–0.574, no
single-family winner; residuals do not transfer their synthetic dominance),
plus episode deduplication and a 24 h per-series page budget that cut alerts
20–30× while *improving* range-F1 in every cell (headline config 1,609 → 80
pages, range-F1 0.157 → 0.315, recall 0.729 → 0.562) — the wave-15 tuning:
the alert operating point selected per family on train-side validation
(inner 80/20 split of each train window, 6 windows / 5 series), evaluated
once on NAB test. IsolationForest adopts (0.5%, 24 h) and transfers
(budgeted 80 → 46 pages, range-F1 0.315 → 0.382); LOF keeps the default;
OCSVM's marginal adoption fails to transfer (−0.043/+0.033 test F1) — the
measured limit of 6-window validation evidence, published as such — and the
wave-16 rank-average ensemble: it wins the sweep at the frozen default
(35 pages at range-F1 0.533 and recall 0.604 on the rolling cell, versus
66 pages at 0.388 for IsolationForest), needs no operating-point tuning
(flat validation surface, +0.010 at best), and lifts budgeted range precision
to 0.553; the NSL-KDD probe is now byte-reproducible (deterministic
categorical factorization, 0.8877 / 0.8979) — the wave-17 refinement
ablation then challenged the detector layer itself at the fixed 2% budget
(`nab-refine`, artifact `reports/nab_refinement.json`): conformal
hour-of-week calibration, IF+LOF rank fusion, and normalized fusion all
failed the adoption gate (precision@budget and range-F1 must improve while
coverage holds at 16/17 — calibration spends ≈2.4× the face budget before
scoring, fusion reaches range-F1 0.403 at 14/17 coverage), so the committed
detector stands, published as a designed negative result. What remains:

- **Recalibrate the adaptive drift trigger on real data** — the median/IQR
  trigger tuned on synthetic fires on 26% of NAB chunks; it needs a
  higher z threshold or a variance-normalised statistic before production use.
- **Range precision is still the wall** (0.05–0.12 raw across the sweep) —
  unattended paging stays deferred until real-data precision improves. The
  wave-17 ablation closed the cheapest detector-layer exits (context
  calibration, rank fusion): precision gains exist, but only by surrendering
  incident coverage or the alert budget.
