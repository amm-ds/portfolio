# 12 — Tabular ML & Deep Learning Lifecycle (UCI Bike Sharing, hourly)

## Protocol

Time-based split: the final 8 weeks of the 2011-2012 hourly series are the test window; the 8 weeks before it are validation (model selection, LightGBM HPO, MLP early stopping and shipped ablation configuration); everything earlier is training. Each candidate receives one test score. Ablation variants are also test-scored only after freezing and are labeled post-freeze diagnostics. The served-model-vs-floor MAE gap uses paired hourly bootstrap resampling, with paired non-overlapping 24-hour and 168-hour block bootstraps as serial-dependence sensitivity analyses.

## Frozen test window

| candidate | test MAE | test RMSE | test MAPE % |
|---|---|---|---|
| seasonal naive (floor) | 83.2 | 134.0 | 153.2 |
| ridge | 51.1 | 77.8 | 86.4 |
| random forest | 26.3 | 45.7 | 25.7 |
| LightGBM (Optuna HPO) | 25.4 | 40.2 | 27.4 |
| tabular MLP (PyTorch) | 25.4 | 39.3 | 33.7 |

Validation-selected model: **mlp** — MAE improvement vs floor +57.8, hourly 95% CI [52.5, 63.1], significant_95=True. Serial-dependence sensitivity (95% CI): hourly: [52.5, 63.1]; day: [44.2, 71.8]; week: [38.8, 73.4].

## Post-freeze MLP regularization diagnostics (2x2x2)

Validation selected the shipped configuration before test scoring. These test scores are diagnostics, never selectors.

| dropout | weight decay | early stopping | val MAE | post-freeze test MAE |
|---|---|---|---|---|
| on | on | on | 34.2 (shipped) | 25.4 |
| on | on | off | 35.3 | 26.8 |
| on | off | on | 34.3 | 25.4 |
| on | off | off | 34.8 | 26.2 |
| off | on | on | 32.1 | 25.0 |
| off | on | off | 35.7 | 27.4 |
| off | off | on | 32.2 | 25.0 |
| off | off | off | 34.8 | 27.3 |

## Limits

- Model selection, early stopping and the shipped ablation configuration used validation only. Test scores for all ablation variants are post-freeze diagnostics, not selection evidence.
- Hourly errors are serially dependent. Day/week block bootstraps are sensitivity analyses on the same test window, not independent confirmations.
- MAPE denominators are floored at 1 rental; near-zero hours inflate MAPE even when the absolute error is small — read MAE first.
- Two years and four seasons, one city, one system: transfer to other fleets or regimes is plausible, not measured.

Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, `reports/train_runs.json`, `reports/evaluation_metadata.json`.
