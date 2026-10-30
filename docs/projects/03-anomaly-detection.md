# 03 · Anomaly Detection over Telemetry

**Domain:** anomaly detection / systems monitoring · **Data:** Numenta Anomaly
Benchmark (12 series; seeded synthetic telemetry as the labelled CI fast path;
NSL-KDD transfer probe) · **Status:** working showcase

> On NAB at a fixed 2% alert budget, IsolationForest catches 16 of 17
> labelled incident windows but fires 1,609 alerts. Deduplication plus a
> one-page-per-day cap cuts that to 80 pages at modest recall cost—page the
> alert stream, not the detector score.
>
> On-call engineers pay for missed incidents in outage multiples and for
> false pages in alert fatigue — the detector choice is a budget question.
> On real NAB telemetry the champion finds 16 of 17 labelled events (range
> recall 0.729), but at 0.107 range precision the firehose is the finding —
> and the delivered fix is a page budget: episode dedup + a 24 h per-series
> cap cut alerts 1,609 → 80 while *raising* range-F1 0.157 → 0.315.
>
> [Case study source and interactive figures on GitHub →](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection)

Unsupervised anomaly detection, **real data first**: 12 series from the
[Numenta Anomaly Benchmark](https://github.com/numenta/NAB) (AWS CloudWatch,
traffic sensors, known-cause system failures; [dataset
card](https://amm-ds.github.io/portfolio/data-registry/nab/)) evaluated with
event-based metrics — PR-AUC and range-F1 lead, ROC-AUC secondary. A seeded
synthetic telemetry stream (CPU, memory, latency) remains the clearly-labelled
CI / fast path. Three classical detectors compete behind data-quality gates
with time-ordered splits, seeded HPO, adaptive-threshold streaming, residual
features, and an NSL-KDD transfer probe.

Working showcase on the standard platform — see the project
[README](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection/README.md) for the full write-up
and [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection/DESIGN.md) for the
detector-failure and real-vs-synthetic analysis.

## NAB headline (event-based, 9 of 12 series evaluable)

*How to read: PR-AUC rewards alerts inside labelled windows; range-F1 scores
whole events; "events" = detected/total with the alert count at a fixed 2%
budget; bold = overall champion.*

![Six representative NAB series (2×3 panels, series id per panel): most of the 897 alerts miss the amber event windows — nyc_taxi misses one labelled event, the other five detect theirs](../assets/projects/03-anomaly-detection/nab_timelines.png){ width="100%" }

| family | PR-AUC | range-F1 | range prec./rec. | events |
|---|---|---|---|---|
| realAWSCloudwatch | 0.404 | 0.088 | 0.049 / 0.500 | 3/3, 132 alerts |
| realKnownCause | 0.438 | 0.074 | 0.040 / 0.938 | 8/9, 1 289 alerts |
| realTraffic | 0.728 | 0.310 | 0.232 / 0.750 | 5/5, 188 alerts |
| **overall** | **0.527** | **0.157** | **0.107 / 0.729** | **16/17, 1 609 alerts** |

The event-window verdict leads: 16 of 17 labelled windows detected (range
recall 0.729) at 0.107 range precision — 1 609 alerts for 16 events. A
detector × feature sweep on NAB (12 series × IsolationForest/LOF/OCSVM ×
rolling vs rolling+residual features, all untuned at the same train-anchored
2% threshold) leaves **no winner**: pointwise PR-AUC spans 0.515–0.574 (best
is LOF on rolling+residual, 0.574; the headline IsolationForest+residual
recipe sits at 0.527), raw range recall 0.688–0.750 with 1 609–3 586 alerts
emitted — rolling-median residuals do **not** transfer their synthetic
dominance to real incidents. The deliverable is therefore the alert-budget
layer, not a different detector: episode dedup + a 24 h per-series cap cut
pages 20–30× and *raise* range-F1 in every sweep cell, because most raw
pages were burst re-alerts inside incidents:

| sweep cell (raw → budgeted) | alerts | range recall | range-F1 |
|---|---|---|---|
| isolation_forest + rolling | 1,864 → 66 | 0.729 → 0.604 | 0.154 → 0.388 |
| isolation_forest + rolling_residual | 1,609 → 80 | 0.729 → 0.562 | 0.157 → 0.315 |
| lof + rolling | 3,263 → 109 | 0.750 → 0.542 | 0.086 → 0.213 |
| lof + rolling_residual | 3,586 → 122 | 0.750 → 0.542 | 0.088 → 0.200 |
| ocsvm + rolling | 2,412 → 87 | 0.688 → 0.521 | 0.086 → 0.281 |
| ocsvm + rolling_residual | 2,253 → 91 | 0.688 → 0.438 | 0.102 → 0.214 |

The cross-detector winner claim lives on the synthetic ladder only — tuned
IsolationForest by ROC-AUC (0.9171), tuned OCSVM by PR-AUC (0.1355). The
honest delta vs. the synthetic track (ROC-AUC 0.916, residuals 0.9999):
injected synthetic anomalies are trivially separable; LOF's local-density
blindness is structural and tuning-resistant. New: a downsampled
single-series interactive timeline, `nab_timeline_nyc_taxi`
(3 of 4 labelled windows detected, 179 alerts), makes the one real miss
hoverable.

**The operating point is now tuned, train-side only (wave 15).** The (alert
budget, per-series cooldown) pair is selected per detector family on an inner
80/20 split of each series' train window — the budgeted alert stream is
scored on the 6 labelled windows overlapping those validation slices, and a
grid point is adopted only when it beats the documented (2%, 24 h) default by
≥ 0.05 validation range-F1; the NAB test window is then scored exactly once
per family (artifact `reports/nab_tune.json`, figure `nab_tune_surface`).
Measured verdict: IsolationForest adopts (0.5%, 24 h) and the gain transfers
— budgeted pages 66 → 33 (rolling) and 80 → 46 (rolling+residual), range-F1
0.388 → 0.433 / 0.315 → 0.382 at ≈0.08–0.10 of range recall. LOF keeps the
default (flat validation surface). OCSVM's marginal adoption (0.5%, 72 h)
fails to transfer (−0.043/+0.033 test range-F1): six validation windows
cannot certify a fragile peak — published as the measured limit of the
evidence, not silently rolled back (that would be test-origin tuning).

## Artifacts

- NAB metrics: `reports/nab_metrics.json` · NAB sweep + alert budgets: `reports/nab_sweep.json` · train-side operating-point tuning: `reports/nab_tune.json` · synthetic ladder: `reports/metrics.json` (7 runs)
- Probes: `reports/detect.json` (adaptive stream), `reports/residual_probe.json`,
  `reports/nsl_probe.json`
- Evaluation report: `reports/report.html`
- Figures: interactive versions live in the [case study on GitHub](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection);
  static artifacts (HTML + JSON) in `reports/figures/`
- DQ report: `reports/dq_report.html` — 8/8 gates passing

## Pipeline

`prepare → validate → features → train → tune → evaluate → detect →
residuals → nsl → nab`, each a Typer command (`uv run python -m
anomaly_detection.cli all` runs everything) and a DVC stage
(`dvc repro projects/03-anomaly-detection`).
