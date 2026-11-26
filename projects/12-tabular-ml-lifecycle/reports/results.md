# 12 — Tabular ML & Deep Learning Lifecycle (UCI Bike Sharing, hourly)

## Protocol

Time-based split: the final 8 weeks of the 2011-2012 hourly series are the test window; the 8 weeks before it are validation (model selection, LightGBM HPO, MLP early stopping and shipped ablation configuration); everything earlier is training. Each candidate receives one test score. Ablation variants are also test-scored only after freezing and are labeled post-freeze diagnostics. The served-model-vs-floor MAE gap uses paired hourly bootstrap resampling, with paired non-overlapping 24-hour and 168-hour block bootstraps as serial-dependence sensitivity analyses.

## Frozen test window

| candidate | test MAE | test RMSE | test MAPE % |
|---|---|---|---|
| seasonal naive (floor) | 73.0 | 120.0 | 129.9 |
| ridge | 48.7 | 72.2 | 101.1 |
| random forest | 26.1 | 42.4 | 62.5 |
| LightGBM (Optuna HPO) | 23.8 | 37.1 | 53.3 |
| tabular MLP (PyTorch) | 27.2 | 40.4 | 47.7 |

Validation-selected model: **lightgbm_hpo** — MAE improvement vs floor +49.2, hourly 95% CI [44.4, 54.0], significant_95=True. Serial-dependence sensitivity (95% CI): hourly: [44.4, 54.0]; day: [37.4, 61.2]; week: [33.0, 63.8].

## Post-freeze MLP regularization diagnostics (2x2x2)

Validation selected the shipped configuration before test scoring. These test scores are diagnostics, never selectors.

| dropout | weight decay | early stopping | val MAE | post-freeze test MAE |
|---|---|---|---|---|
| on | on | on | 35.1 (shipped) | 27.2 |
| on | on | off | 32.8 | 24.7 |
| on | off | on | 35.2 | 27.2 |
| on | off | off | 33.4 | 24.8 |
| off | on | on | 29.6 | 23.6 |
| off | on | off | 32.6 | 25.4 |
| off | off | on | 29.5 | 23.4 |
| off | off | off | 33.1 | 26.1 |

## Limits

- Model selection, early stopping and the shipped ablation configuration used validation only. Test scores for all ablation variants are post-freeze diagnostics, not selection evidence.
- Hourly errors are serially dependent. Day/week block bootstraps are sensitivity analyses on the same test window, not independent confirmations.
- MAPE denominators are floored at 1 rental; near-zero hours inflate MAPE even when the absolute error is small — read MAE first.
- Two years and four seasons, one city, one system: transfer to other fleets or regimes is plausible, not measured.

Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, `reports/train_runs.json`, `reports/evaluation_metadata.json`.
