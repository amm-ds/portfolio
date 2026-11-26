# Phase 3 result — project 12 corrected-variant MLP scratch rerun

Date: 2026-11-26. Executor: Kimi Code (subagent). Scope: scratch-only rerun of the
E4 sensitivity path for `projects/12-tabular-ml-lifecycle`; CPU only, zero hosted
calls, no promotion. The one repo file written by this phase is this document.

## Isolation record

- Fresh scratch copy: `rsync -a projects/12-tabular-ml-lifecycle/ scratchpad/e12_v2_rerun/`
  (directory created for this phase). `scratchpad/e12_v2` was never read or cited.
- Data: `data/*` is gitignored (project `.gitignore` line 5; only
  `data/feature_selection.json` is committed). `rsync -a` copied the local
  gitignored payloads, including `data/hour.parquet` — the only data input the
  sensitivity arm reads (`run_ladder_arm` reads the committed prepared frame; it
  does not fetch). Plain copies, no symlinks needed.
- Execution: repo `.venv` Python 3.12.9 with `PYTHONPATH=scratchpad/e12_v2_rerun/src`
  so the scratch copy's own source executed (verified via
  `tabular_ml_lifecycle.__file__`), CWD = scratch copy so the CWD-relative
  `data_dir`/`reports_dir` (`config.py:124-125`) resolved inside the copy.
- Command (per run, from the scratch copy):
  `python -m tabular_ml_lifecycle.cli sensitivity --params-file params.yaml --variant-params-file params_variant.yaml`
  — the committed E4 entry point (`sensitivity.py:205 run_sensitivity`, ladder arm
  `:112 run_ladder_arm`).
- Writes landed only in the scratch copy (`reports/sensitivity_pruning_lags.json`
  + figure, plus `run{1,2,3}.{json,log}` evidence copies). Post-run
  `git status --short projects/12-tabular-ml-lifecycle projects/13-model-serving`
  shows only the two pre-existing modifications (`README.md`, `story.yaml`) that
  were present before this phase; no committed file in projects 12 or 13 changed.

## Gate 1 — v1 reproduction (committed `params.yaml`, sensitivity path)

Checked inside every run (the CLI aborts with `ReproductionError` on failure; all
three runs exited 0). Values identical across runs:

| check | expected | derived | abs diff | tolerance | result |
|---|---|---|---|---|---|
| MLP test MAE | 25.4316 (committed `metrics.json`: 25.43163249606178) | 25.43163249606178 | 0.0 | 1e-4 | PASS |
| LightGBM test MAE | 25.3732 (committed `metrics.json`: 25.37318492658977) | 25.37318492658977 | 1.5e-05 vs rounded target; 0.0 vs committed value | 1e-4 | PASS |

The artifact's `committed.rederived_max_abs_diff` across all five models is 0.0 —
the committed run reproduces exactly.

## Gate 2 — corrected-variant rerun (`params_variant.yaml`, same sensitivity path, seed 42)

| run | MLP test MAE | LightGBM test MAE | seasonal-naive test MAE | runtime_s |
|---|---|---|---|---|
| 1 | 27.161182233265468 | 23.76360139335002 | 72.97619047619048 | 105.97 |
| 2 | 27.161182233265468 | 23.76360139335002 | 72.97619047619048 | 89.24 |
| 3 | 27.161182233265468 | 23.76360139335002 | 72.97619047619048 | 79.17 |

All three runs are bit-identical (also bit-identical to the committed E4
artifact's `variant.test_mae`/`val_mae`): the corrected variant is fully
deterministic under seed 42 on this host.

- **Spread rule:** MLP range = max − min = 0.0 ≤ 0.10 → PASS.
  **v2 = median = 27.161182233265468 ≈ 27.16.**
- **Naive check:** variant seasonal naive = 72.97619047619048 vs E4's 72.98,
  |diff| = 0.0038 ≤ 0.5 → PASS. It is decisively not ~83.20 (the positional-path
  value), confirming the timestamp/keep_higher_mi path. Run log:
  `arm (timestamp/keep_higher_mi): test MAE floor=72.98 ... lgbm=23.76 mlp=27.1612`.

## Side-by-side

| model | committed v1 (`metrics.json`) | E4 arm (committed artifact) | this rerun (median of 3) |
|---|---|---|---|
| MLP test MAE | 25.4316 | 27.16 | 27.1612 |
| LightGBM test MAE | 25.3732 | 23.76 | 23.7636 |
| seasonal-naive test MAE | 83.1994 | 72.98 | 72.9762 |

The rerun reproduces the E4 arm exactly; the corrected-variant MLP number is
stable.

## Validation-selection observation (input to the owner's Phase 4 decision)

Variant validation MAE, identical in all three runs: LightGBM **31.9391** vs MLP
**35.1311** (seasonal naive 62.3582, ridge 56.6258, random forest 36.2332).
Validation selection under v2 picks **LightGBM**, confirming the E4 arm's
suggestion (31.9 vs 35.1) — not the MLP. If v2 were promoted with val-based
model selection, the served model would change from MLP (v1 test 25.4316) to
LightGBM (v2 test 23.7636).

## Wall time

20:56:22 → 21:01:15 local (4 min 53 s total for three runs; per-run runtimes
above, slower than E4's 55.2 s due to concurrent load on the host — numbers
unaffected).

Phase 3 complete. Stopped before any promotion; no committed file in projects 12 or 13 was changed.
