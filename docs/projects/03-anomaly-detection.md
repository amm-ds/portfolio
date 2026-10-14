# 03 — Anomaly Detection over Telemetry

Unsupervised detection of anomalous minutes in server telemetry (CPU, memory,
latency). Three classical detectors — IsolationForest, LOF, One-Class SVM —
compete on a seeded synthetic stream (n = 20 000, 2% injected anomalies) behind
explicit data-quality gates, with a time-ordered train/test split and a fixed
contamination threshold.

Working showcase on the standard platform — see the project
[README](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection/README.md) for the full write-up
and [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection/DESIGN.md) for the
detector-failure analysis.

## Key results (seed 42, test window = 5 983 rows, prevalence 1.89%)

| run | ROC-AUC | PR-AUC |
|---|---|---|
| random (seeded baseline) | 0.509 | 0.019 |
| lof (untuned) | 0.527 | 0.019 |
| ocsvm (untuned) | 0.337 | 0.024 |
| lof_tuned | 0.505 | 0.025 |
| ocsvm_tuned | 0.906 | **0.136** |
| isolation_forest (untuned) | 0.916 | 0.124 |
| isolation_forest_tuned | **0.917** | 0.121 |

Champion by PR-AUC: `ocsvm_tuned` — tuning rescued One-Class SVM
(`gamma=0.013` vs. the failing `scale` default); LOF was *not* rescued
(structural local-density blindness). IsolationForest was near-optimal
untuned. At the fixed 2% alert budget the three top detectors tie
(~15% recall / ~14% precision). adaptive-threshold
streaming (0 drift events on the stable test stream; 113 vs. 120 flags at
equal ~15% precision), rolling-median residual features (IsolationForest
ROC-AUC 0.9158 → 0.9999 — the anomaly blob de-clusters), and the NSL-KDD
transfer probe (0.8817 ROC-AUC / 0.8916 PR-AUC on 22 544 real network-flow
records). Full analysis in
[DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/03-anomaly-detection/DESIGN.md).

## Artifacts

- Metrics: `projects/03-anomaly-detection/reports/metrics.json` (7 runs)
- Probes: `reports/detect.json` (adaptive stream), `reports/residual_probe.json`,
  `reports/nsl_probe.json`
- Evaluation report: `reports/report.html`
- Figures (`reports/figures/`): `eda_signals_overview`, `roc_curves`,
  `pr_curves`, `telemetry_flags`, `score_distribution`, `threshold_sweep`,
  `hpo_importance`, `adaptive_stream` (HTML + JSON for the showcase API)
- DQ report: `reports/dq_report.html` — 8/8 gates passing

## Pipeline

`prepare → validate → features → train → tune → evaluate → detect →
residuals → nsl`, each a Typer command (`uv run python -m
anomaly_detection.cli all` runs everything, ~80 s including 90 seeded HPO
trials and the NSL-KDD download) and a DVC stage
(`dvc repro projects/03-anomaly-detection`).
