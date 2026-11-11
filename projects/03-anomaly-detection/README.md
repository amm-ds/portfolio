# 03 — Anomaly Detection over Telemetry

Unsupervised anomaly detection on 12 labelled Numenta Anomaly Benchmark (NAB)
series, with a seeded synthetic telemetry stream for offline CI. The current
comparison covers IsolationForest, Local Outlier Factor (LOF), One-Class SVM,
and a rank-average ensemble under time-ordered splits and explicit alert budgets.

The primary question is operational: how many incidents are detected, and how
many pages does the team receive? Pointwise PR-AUC stays separate from
event-aware range-F1.

## Reproduce

```bash
# from the repository root
uv run python -m anomaly_detection.cli all          # synthetic pipeline
uv run python -m anomaly_detection.cli nab          # NAB headline track
uv run python -m anomaly_detection.cli nab-sweep    # detector × feature sweep + alert budgets
uv run python -m anomaly_detection.cli nab-tune     # train-side operating-point selection
uv run python -m anomaly_detection.cli nab-refine   # detector-layer refinement ablation

# synthetic pipeline, stage by stage
uv run python -m anomaly_detection.cli prepare
uv run python -m anomaly_detection.cli validate
uv run python -m anomaly_detection.cli features
uv run python -m anomaly_detection.cli train
uv run python -m anomaly_detection.cli tune
uv run python -m anomaly_detection.cli evaluate

# or via DVC
dvc repro projects/03-anomaly-detection

# offline tests
uv run pytest projects/03-anomaly-detection -q
```

## Design

The synthetic pipeline prepares 20,000 seeded telemetry rows at a 2% injection
rate, enforces data-quality gates, builds rolling features, and trains on the
first 70% of the timeline. Optuna tuning uses only a validation slice inside
that train window. Evaluation uses the final 30% and a fixed alert threshold.

The NAB track uses checksum-pinned series from `realAWSCloudwatch`,
`realKnownCause`, and `realTraffic`. Three series have no labelled window in
the test split and are excluded from aggregates. The remaining nine series use
the same 70/30 time split and a train-anchored 2% alert budget.

Alert streams have three forms: raw pages for every flagged minute, one page
per contiguous episode, and deduplicated pages capped at one per series per
24 hours. See [DESIGN.md](DESIGN.md) for alternatives, failure analysis, and
the experiment history.

## Results

### NAB primary track

The IsolationForest headline run scores **PR-AUC 0.527** and **range-F1
0.157** on the evaluable test windows. It touches **16 of 17 incident windows**
but emits **1,609 raw alerts**. Episode deduplication and the 24-hour cap cut
that load to **80 pages** and raise range-F1 to **0.315**, with range recall
moving from 0.729 to 0.562.

A threshold sweep under the project's window matching puts the headline on a
no-skill footing: the champion's **range-PR area is 0.804** against a 16-seed
random band at **0.228 [0.081, 0.401]**, and **precision at a 2% alert budget
is 0.527** (recall 0.944) against a no-skill **0.082 [0.063, 0.105]** — six
times the no-skill precision while still touching nearly every window. At 0.5%
of the stream precision reads 0.680; at 5%, 0.234 (see `reports/nab_metrics.json
→ no_skill` and the `range_pr` figure).

The current rank-average ensemble uses rolling features and the frozen 2%
budget with a 24-hour cap. It improves the operating point without selecting
on the test window.

| detector and stream | alerts | range recall | range-F1 |
|---|---:|---:|---:|
| IsolationForest + rolling residual, raw | 1,609 | 0.729 | 0.157 |
| IsolationForest + rolling residual, budgeted | 80 | 0.562 | 0.315 |
| IsolationForest + rolling, budgeted and train-tuned | 33 | 0.500 | 0.433 |
| **rank-average ensemble + rolling, budgeted** | **35** | **0.604** | **0.533** |

The ensemble's train-side validation surface does not clear the adoption
margin for changing its default operating point. The default therefore remains
(2%, 24 h). Full per-family and per-feature results are in
[`reports/nab_sweep.json`](reports/nab_sweep.json); tuning evidence is in
[`reports/nab_tune.json`](reports/nab_tune.json).

A separate refinement ablation rejects conformal context calibration and two
IF+LOF fusion variants. They fail the joint precision, range-F1, and 16/17
coverage gate. The negative result and exact cells are committed in
[`reports/nab_refinement.json`](reports/nab_refinement.json).

### Synthetic CI track

The seeded synthetic test window contains 5,983 rows at 1.89% prevalence.
These measurements validate pipeline behavior; they do not estimate real
incident-page load.

| run | ROC-AUC | PR-AUC |
|---|---:|---:|
| random baseline | 0.5091 | 0.0194 |
| IsolationForest, untuned | 0.9158 | 0.1239 |
| IsolationForest, tuned | **0.9171** | 0.1208 |
| One-Class SVM, tuned | 0.9056 | **0.1355** |

Rolling-median residuals lift synthetic IsolationForest to 0.9999 ROC-AUC and
0.9960 PR-AUC, but that gain does not transfer to NAB. This non-transfer is a
central limit of the synthetic evidence.

Artifacts: [`reports/metrics.json`](reports/metrics.json),
[`reports/nab_metrics.json`](reports/nab_metrics.json),
[`reports/report.html`](reports/report.html), and `reports/figures/`. The NAB
figures cover representative timelines, score distributions, alert budgets,
and the tuning surface.

## Limits

Raw range precision remains too low for unattended paging. The 24-hour cap is
an operating assumption, and operating-point tuning sees only six validation
windows. The synthetic track cannot rank detectors by real-world precision.

The adaptive drift trigger fires on 31 of 120 NAB chunks, so its synthetic
median/IQR calibration needs real-data recalibration. NSL-KDD remains a
labelled transfer probe with 56.9% prevalence, not evidence for the 2% telemetry
operating regime.

## Common errors

| symptom | cause | fix |
|---|---|---|
| `cli nab`, `nab-sweep`, `nab-tune`, or `nab-refine` fails fetching | the NAB real track downloads its checksum-pinned subset on first run (`data/nab/` is a stage out, not committed data) | run once with network: `uv run python -m anomaly_detection.cli nab`; alternatively restore via `uv run dvc repro projects/03-anomaly-detection`; offline work stays on the synthetic track and tests |
