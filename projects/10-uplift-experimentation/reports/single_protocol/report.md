# Q4a single-protocol uplift comparison

Generated: 2026-11-19T12:34:20.951089+00:00 · n = 42613 rows · outcome: conversion · committed folds (cfg.seed=42, cv_folds=5, OOF convention)

Qini area (AUUC), unnormalised — area between the incremental-conversions curve and the random line (unnormalised; qini.qini_coefficient == AUQC - AUQC(random)).

| learner | Qini area (AUUC) | 95% bootstrap CI |
|---|---|---|
| causal_forest | -3.5258 | [-16.2121, 9.7036] |
| t_learner_two_model | 12.0252 | [-0.0135, 24.1773] |
| x_learner | 5.9040 | [-6.0967, 17.8957] |

Notes:
- Causal forest: hand-rolled DR-learner forest (sklearn RandomForestRegressor on DR pseudo-outcomes, cross-fitted on the committed folds; no grf/econml, per DESIGN.md no-heavyweight-deps).
- the two-model approach and the T-learner are the same estimator family; one committed OOF column carries both labels.
- DR pseudo-outcome: psi = (mu1-mu0) + T(y-mu1)/g - (1-T)(y-mu0)/(1-g).
- DR policy value by budget (with intervals) is in `metrics.json` per learner.
- New files only; no committed record was modified.
