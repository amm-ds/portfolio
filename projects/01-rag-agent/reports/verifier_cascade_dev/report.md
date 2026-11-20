# Verifier cascade DEV calibration report

Generated: 2026-11-20T00:59:52.609850+00:00 (commit `d9730106c9c8d38d7ef3507b2e7f89dcba2f6a4c`)

- Grid: 4095 bands over 91 unique DEV MiniCheck scores; folds: 5-fold stratified by label, seed 42
- CV qualifying bands (FA <= 0.10 AND FR <= 0.10): 0 of 4095

## No qualifying band

No (t_lo, t_hi) grid band met FA <= 0.10 AND FR <= 0.10 on cross-validated DEV. TEST was not read.

## Extremes over all bands

- Lowest CV FA: t=[0.9799, 0.9814] FA 0/48 = 0.0 FR 44/48 = 0.9167 deferred 0/96 = 0.0
- Lowest CV FR: t=[0.0629, 0.9410] FA 7/48 = 0.1458 FR 0/48 = 0.0 deferred 2/96 = 0.0208
- Lowest CV deferred share: t=[0.0839, 0.9410] FA 7/48 = 0.1458 FR 0/48 = 0.0 deferred 0/96 = 0.0

Runtime 0.09 s, no hosted calls ($0).
