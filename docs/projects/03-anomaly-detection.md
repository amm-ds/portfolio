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

| model | ROC-AUC | PR-AUC |
|---|---|---|
| isolation_forest | **0.9158** | **0.124** |
| lof | 0.5272 | 0.019 |
| ocsvm | 0.3368 | 0.024 |
| random (seeded baseline) | 0.5091 | 0.019 |

IsolationForest beats the seeded random baseline by +0.41 ROC-AUC; LOF/OCSVM
sit at or below it because the injected anomalies form a compact self-similar
cluster that local-density and boundary detectors cannot see — analyzed with
k-NN distance evidence in DESIGN.md.

## Artifacts

- Metrics: `projects/03-anomaly-detection/reports/metrics.json`
- Evaluation report: `reports/report.html`
- Figures (`reports/figures/`): `eda_signals_overview`, `roc_curves`,
  `pr_curves`, `telemetry_flags` (HTML + JSON for the showcase API)
- DQ report: `reports/dq_report.html` — 8/8 gates passing

## Pipeline

`prepare → validate → features → train → evaluate`, each a Typer command
(`uv run python -m anomaly_detection.cli all` runs everything in ~2 s) and a
DVC stage (`dvc repro projects/03-anomaly-detection`).
