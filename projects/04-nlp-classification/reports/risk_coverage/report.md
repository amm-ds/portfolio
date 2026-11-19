# Q4b risk-coverage / AURC — distilbert_full_120k on the fresh holdout

Generated: 2026-11-19T12:48:34.569447+00:00 · n = 1000 · confidence: max softmax probability

- Fresh macro-F1 recomputed 0.9529432 == committed 0.9529432 (identity verified).
- **AURC = 0.0068**, bootstrap 95% [0.0037, 0.0106] (mean risk over the coverage sweep; lower is better).

| coverage (most-confident prefix) | risk (1 - accuracy) |
|---|---|
| 1.00 | 0.0470 |
| 0.90 | 0.0178 |
| 0.75 | 0.0093 |
| 0.50 | 0.0020 |
| 0.25 | 0.0000 |

New files only; no committed record modified. Full curve in `metrics.json`.
