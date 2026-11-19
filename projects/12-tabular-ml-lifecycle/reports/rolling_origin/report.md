# Rolling-origin check — MLP vs LightGBM on the committed validation window

Generated: 2026-11-19T14:22:42.385947+00:00 - 8 weekly origins x 168 rows · committed artifacts, no retraining.

Identity: full-window validation MAE recomputed == committed `train_runs.json` for both models.

| origin week | MLP MAE | LightGBM MAE | diff (MLP - LGBM) | 95% CI |
|---|---|---|---|---|
| 0 | 32.509 | 31.595 | +0.915 | [-5.441, +5.560] |
| 1 | 30.044 | 30.029 | +0.015 | [-3.150, +3.128] |
| 2 | 30.733 | 31.049 | -0.315 | [-2.463, +3.390] |
| 3 | 39.166 | 37.437 | +1.729 | [-6.510, +1.583] |
| 4 | 36.364 | 35.956 | +0.408 | [-5.821, +3.917] |
| 5 | 39.098 | 38.940 | +0.158 | [-4.875, +4.437] |
| 6 | 32.957 | 31.086 | +1.871 | [-5.462, +0.719] |
| 7 | 32.864 | 39.083 | -6.218 | [+2.700, +10.142] |

Pooled across origins: diff -0.180 MAE [-1.367, +1.854] (day-block bootstrap, 24 h blocks).
Committed tie (both CIs include zero across the window) holds: **True**.

New files only; `reports/metrics.json` untouched.
