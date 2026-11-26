# Vendored: official NAB scorer (numenta/NAB)

- **Upstream:** https://github.com/numenta/NAB
- **Pinned commit:** `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140` (`master` at fetch time, 2026-11-26)
- **License:** MIT — see `LICENSE-nab.txt` (verbatim copy of upstream `LICENSE.txt`)
- **Citation:** Ahmad, Lavin, Purdy & Agha (2017), "Unsupervised real-time
  anomaly detection for streaming data", Neurocomputing 262:134-147.

## Files

| file | upstream source at the pinned commit | how vendored |
|---|---|---|
| `nab_scorer.py` | `nab/sweeper.py`, `nab/optimizer.py`, `nab/scorer.py`, `nab/runner.py` (`normalize`), `nab/detectors/null/null_detector.py` | hand port to Python 3 + stdlib (see below) |
| `nab_profiles.json` | `config/profiles.json` | byte-verbatim copy (standard, reward_low_FP_rate, reward_low_FN_rate) |
| `nab_combined_windows.json` | `labels/combined_windows.json` | byte-verbatim copy; sha256 `1e1fbc4601321aad8d0f8b3784c8134299379f68f6c1f7777565f8ffd57ab6b1`, identical to the checksum `nab.py` pins for the fetched labels |
| `LICENSE-nab.txt` | `LICENSE.txt` | byte-verbatim copy |

## Port notes (what changed relative to upstream)

- **Python 3 + stdlib only.** Upstream's pandas DataFrames, multiprocessing
  pool, and `simplejson` fallback are replaced by plain sequences and dicts.
  No third-party imports; nothing here touches the network.
- **Identifiers are snake_case** (`calcSweepScore` → `calc_sweep_score`,
  `optimizeThreshold` → `optimize_threshold`, ...); each function docstring
  names its upstream source. The scoring math — sigmoid scaling, window
  credit as the per-window max, `-fnWeight` window initialization, FP
  accumulation, the 1.1 initial sweep threshold, the stable descending sort
  in threshold optimization, and `100 * (raw - null) / (perfect - null)`
  normalization — is line-for-line faithful.
- **`timestamps.index(bound)` becomes a first-occurrence index map.** With
  the unique timestamps this project feeds the scorer the two agree; the port
  raises `ValueError` on window bounds missing from the timestamps (upstream
  raised `ValueError` from `list.index`).
- **`assert` became `raise ValueError`** (repo lint forbids `assert` outside
  tests).
- **Type annotations added** throughout.
- The null baseline emits the upstream NullDetector's constant 0.5; the
  perfect baseline is NAB's analytic `tpCount * tpWeight` (upstream
  `Runner.normalize`), with a helper that constructs detector scores firing
  only at window starts so the sanity gate can reproduce 0 and 100 through
  the full optimize → score → normalize path.

## How this project uses the scorer

`anomaly_detection.nab_official` feeds the scorer the nine evaluable NAB
series' committed IsolationForest test-span scores (recomputed exactly as
`anomaly_detection.nab.evaluate_series` does and verified against the
committed `reports/nab_metrics.json`, including the 1,609 raw-alert total).
The scored span is each series' post-training 30%; the 70% train split plays
the role of NAB's probationary period, so the sweeper runs with
`probation_percent = 0`. One label window (`realKnownCause/nyc_taxi`, first
window) starts inside the train span and is clipped to the first scored
timestamp. The synthetic telemetry stream with injected anomalies is never
part of the official score.
