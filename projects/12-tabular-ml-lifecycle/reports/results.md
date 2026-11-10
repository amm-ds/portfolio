# 12 — Tabular ML & Deep Learning Lifecycle (UCI Bike Sharing, hourly)

## Protocol

Time-based split: the final 8 weeks of the 2011-2012 hourly series are the test window, scored once per candidate; the 8 weeks before it are validation (model selection, LightGBM HPO objective, MLP early stopping, ablation choice); everything earlier is training. Lag features read only the past. Paired bootstrap on the test window prices the champion-vs-floor MAE gap.

## Scored-once test window

| candidate | test MAE | test RMSE | test MAPE % |
|---|---|---|---|
| seasonal naive (floor) | 83.2 | 134.0 | 153.2 |
| ridge | 51.1 | 77.8 | 86.4 |
| random forest | 26.3 | 45.7 | 25.7 |
| LightGBM (Optuna HPO) | 25.4 | 40.2 | 27.4 |
| tabular MLP (PyTorch) | 25.4 | 39.3 | 33.7 |

Champion: **mlp** — MAE improvement vs floor +57.8, 95% CI [52.5, 63.1], significant_95=True.

## MLP regularization ablation (2x2x2)

| dropout | weight decay | early stopping | val MAE | test MAE |
|---|---|---|---|---|
| on | on | on | 34.2 | 25.4 ✅ |
| on | on | off | 35.3 | 26.8 |
| on | off | on | 34.3 | 25.4 |
| on | off | off | 34.8 | 26.2 |
| off | on | on | 32.1 | 25.0 |
| off | on | off | 35.7 | 27.4 |
| off | off | on | 32.2 | 25.0 |
| off | off | off | 34.8 | 27.3 |

## Limits

- The test window is scored once per candidate; model selection, early stopping and the ablation choice used validation only.
- MAPE denominators are floored at 1 rental; near-zero hours inflate MAPE even when the absolute error is small — read MAE first.
- Two seasons, one city, one system: transfer to other fleets or regimes is plausible, not measured.

Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, `reports/train_runs.json`, `reports/evaluation_metadata.json`.
