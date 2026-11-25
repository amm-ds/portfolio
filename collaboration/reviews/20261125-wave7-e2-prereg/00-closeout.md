# Wave 7 closeout: E2 pre-registration owner gate

Date: 2026-11-25  
Executor: Kimi Code  
Branch: `wave7-dynamic-pricing-rl-2026-11-25`  
Base and current HEAD: `18adc59d`  
State: **complete through E2-6; awaiting owner and Claude review/commit**

## Outcome

Implemented S-0 and E2-1 through E2-6 in the required gate order. All final gates are green. No PPO training, model selection beyond the allowed validation baselines, or sealed policy evaluation was run. No commit, push, or merge was performed.

## Final verification

| Check | Result |
|---|---|
| `uv run ruff check .` | Pass |
| `uv run ruff format --check .` | Pass; 938 files already formatted |
| `uv run mypy libs projects apps` | Pass; 262 source files |
| `uv run lint-imports` | Pass; 2 contracts kept, 245 files, 867 dependencies |
| `uv run pytest libs/portfolio-eval projects/15-dynamic-pricing-rl -q` | 43 passed; 85.35% total coverage |

The only test warnings are Gymnasium's warnings about infinite bounds on the demand-history Box. Mypy notes that `sb3_contrib.*` is unused until E2-7; this is non-failing and expected.

## Evidence produced

- Shared interval helpers and tests:
  - `libs/portfolio-eval/src/portfolio_eval/intervals.py`
  - `libs/portfolio-eval/tests/test_intervals.py`
- Calibration and immutable source pins:
  - `projects/15-dynamic-pricing-rl/data/calibration.json` — 600 series
  - `projects/15-dynamic-pricing-rl/data/splits.json` — item/series splits, development specs, sealed specs
  - `projects/15-dynamic-pricing-rl/params.yaml` — source hashes, comparator, frozen P1/P2/P3 block
- Environment, LP, baselines, tuning, and tests under `projects/15-dynamic-pricing-rl/`:
  - `src/dynamic_pricing/{env,bound,baselines,specs,tune,preregister,ledger,benchmark,calibrate,cli}.py`
  - `tests/{test_env,test_baselines,test_calibrate,test_specs,test_tuning,test_preregistration}.py`
- Runtime and evaluation evidence:
  - `reports/env_benchmark.json`
  - `reports/baselines_val.json`
  - `reports/experiment_log.json`
- Complete per-attempt gate history:
  - `collaboration/designs/20261124-next-experiments/04-execution-notes.md`

## Recorded results

- Comparator: **B1**, selected on 300 validation episodes.
- Validation mean normalised profit: B0 0.4111363132; B1 0.5224796739; B2 0.3987918111; B3 0.5014737711.
- B1 tuned action: 6 (1.30 × reference price).
- B2 tuned thresholds: 20% behind plan / 5% ahead of plan.
- Validation violations: zero for B0-B3.
- Vector benchmark over 10,000 transitions per wrapper: DummyVecEnv 47,352.13 steps/s; SubprocVecEnv 57,543.30 steps/s. SubprocVecEnv selected for E2-7.

Pre-registration block SHA-256:

`c94f0f97c37afd2788760356b31d89de8fb3d1790b9fc0685bdbcc15bd9cf627`

Sealed spec SHA-256 values:

| Set | Episodes | Stream | SHA-256 |
|---|---:|---:|---|
| Test | 1,000 | 2 | `fb69ba9b96b0224b1d35273d3894f7eaa0351d6c0de4be392ab54f2ff5fb4746` |
| Stress mean −1.5 | 500 | 3 | `cec1622e42ade7081b9b5ec6b8723669805b573814874ef89581ccc3216efb58` |
| Stress mean −3.5 | 500 | 4 | `128bab06ae88f4c28a790102b8c593dde99b479544f3c595d8956932f60a6731` |

No policy was evaluated on any of these specs.

## Source-data discrepancy for review

The architecture assumed 200 M5 items and 420/90/90 series splits. The pinned snapshot actually contains 308 items and 600 series. The implementation preserves the required 140/30/30 item split with seed 42, producing 267/57/58 train/val/test series, and marks 108 items unassigned. All 600 series are calibrated. This discrepancy is explicit in the execution notes and should be acknowledged in the owner review.

## Owner gate and next action

Review and commit the root configuration/lockfile, shared interval files, project 15 files, and execution notes. `portfolio.yaml` and `story.yaml` remain under ignored `.draft/` until E2-9. After the owner commits the frozen protocol, E2-7 can start; E2-8 remains a separate single sealed-read gate.

The unrelated pre-existing untracked path `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/` remains untouched and is not part of this handoff.
