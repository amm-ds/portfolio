# Wave 7 execution notes: dynamic pricing through pre-registration

Date: 2026-11-25  
Executor: Kimi Code  
Branch: `wave7-dynamic-pricing-rl-2026-11-25` (from `main` at `18adc59d`)  
Scope: S-0 and E2-1 through E2-6 only. No PPO training or sealed reads.

## Protocol

- Execute each step only after the preceding gate is green.
- Keep all work uncommitted for owner and Claude review.
- Read project 02's M5 parquet inputs only; never evaluate a policy on test or stress specs.
- Leave the pre-existing untracked `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/` path untouched.

## Gate log

Results are appended after each commanded gate completes.

### S-0 — shared interval helper

- Initial gate run: **red** at `ruff check libs`; two import-order findings (I001), both auto-fixable. Mypy and pytest did not run in that invocation because the gate is chained with `&&`.
- Fix: import order only; no statistical behavior changed.
- Final gate: **green** in 6.683 s. `ruff check libs`: all checks passed. `mypy libs`: no issues in 20 source files. `pytest libs/portfolio-eval -q`: 20 passed; total coverage 83.18% (required 80%).

### E2-1 — project scaffold

- Created the standard scaffold, renamed its derived package from `dynamic_pricing_rl` to the contracted `dynamic_pricing`, moved `portfolio.yaml` and `story.yaml` into ignored `.draft/`, and added all six requested DVC stages.
- Pinned `gymnasium==1.4.0`, `stable-baselines3==2.9.2`, and `sb3-contrib==2.9.2`; registered `dynamic_pricing` with import-linter and strict mypy.
- `uv sync --all-packages --dev`: **green** in 2.735 s; resolved 350 packages and installed the three requested pins.
- Initial E2-1 gate: **red** at Ruff on one scaffold-generated import-order finding (I001) in `schemas.py`; later commands did not run in that invocation.
- Second E2-1 gate: Ruff green; mypy **red** because the new global `scipy.*` missing-import override made project 02's existing `type: ignore[import-untyped]` unused. Removed only that global override; project 02 remains untouched. The chained import-linter and pytest commands did not run in that invocation.
- Third E2-1 gate: Ruff green; mypy green across 253 source files; import-linter green (2 contracts kept, 2 documented ignored imports); pytest executed the scaffold test but coverage was **red** because the empty-package import collected no library data. Replaced it with a meaningful default-config test.
- Fourth E2-1 gate: static gates remained green; pytest passed but total library coverage was 76.04%, below the root 80% threshold. Extended the scaffold test to exercise the declared `portfolio-eval` dependency as well as project config.
- Fifth E2-1 gate: static gates remained green; both pytest tests passed, but importing `portfolio_eval` also imported plotting/report modules and reduced total coverage to 37.44%. Reverted that probe and replaced it with a focused calibration data-quality report test using the already-loaded `portfolio-core` dependency.
- Final E2-1 gate: **green** in 5.281 s. Ruff passed; mypy found no issues in 253 source files; import-linter kept both contracts; 2 tests passed with 92.71% configured library coverage. Mypy emitted non-failing notes that the currently unused `sb3_contrib.*` and `stable_baselines3.*` override sections have no matching imports yet.

### E2-2 — read-only M5 calibration

- Initial CLI invocation: **red** before any source read because Typer collapsed the sole command into a command-less application. Added an explicit callback so `calibrate` remains a named DVC stage.
- Successful calibration runs: 600 series; source has 308 items. Seeded split: 140/30/30 items, 267/57/58 train/val/test series, with 108 items explicitly unassigned. Both successful runs produced identical summary values; each appended its own ledger row.
- Calibration distributions (min / p25 / median / p75 / max): `base` = 0.184066 / 4.732143 / 7.133242 / 11.006181 / 96.541209; `k` = 0.5 / 0.5 / 1.294808 / 2.875804 / 32.445189; `p_ref` = 0.20 / 0.97 / 1.64 / 2.50 / 14.97.
- Initial static gate: **red** on six Ruff findings (unused import, import order, three long lines, one SIM108). Fixed formatting only.
- Second static gate: Ruff green; mypy **red** on missing PyYAML stubs and a broad Polars `mean()` return type. Added the house-style inline PyYAML suppression and computed the mean through NumPy. Re-ran calibration successfully afterward.
- Final E2-2 gate: **green** in 4.718 s. Ruff passed; mypy found no issues in 26 source files; 7 tests passed with 92.71% configured library coverage. Tests prove item disjointness and exact split sizes, cutoff enforcement, SHA mismatch rejection, all 600 weekday profiles summing to 7, and unchanged source hashes.

### E2-3 — Gymnasium environment and CRN

- Initial static gate: **red** on three Ruff findings (Gymnasium mutable metadata, redundant integer cast, test import order). Fixed without dynamic changes.
- Second static gate: Ruff green; mypy **red** on seven Gymnasium/SB3 interface issues. Renamed the episode property to avoid collision with `gym.Env.spec`, retained Gymnasium's instance `metadata` with a targeted RUF012 suppression, cast the discrete action space to its generic base, and typed vector wrappers as callables. Pytest did not run in that invocation.
- Third static gate: **red** on one benchmark import-order finding; fixed.
- Environment gate: **green** in 6.680 s. Ruff passed; mypy found no issues in 28 source files; 15 tests passed with 92.71% configured library coverage. `check_env` passed; its only warnings were the deliberate infinite Box bounds for demand-history observations.
- Benchmark: **green** in 4.428 s, 10,000 transitions per wrapper with 8 environments. DummyVecEnv 47,352.12818268815 steps/s; SubprocVecEnv 57,543.30362471139 steps/s. Selected **SubprocVecEnv** for E2-7. Used train-series specs only; no policy was evaluated on test or stress specs.

### E2-4 — fluid upper bound and B0-B3

- Initial gate: **red** on one test import-order finding; fixed. Mypy and pytest did not run in that invocation.
- Second gate: Ruff and mypy green (30 source files); pytest **red** after 17 passes. B3's remaining LP became infeasible when inventory was below remaining reference demand because daily mixtures were forced to sum to one. Changed daily mixtures to at most one (an idle/no-sales relaxation) and made B3 break zero-share ties within the action mask.
- Final E2-4 gate: **green** in 22.821 s. Ruff passed; mypy found no issues in 30 source files; 18 tests passed with 92.71% configured library coverage. Zero-noise bound ≥ all four baselines, B3 posterior moved toward the true elasticity, and all four baselines had zero violations over 50 random specs.

### E2-5 and E2-6 — tuning, comparator lock, and pre-registration

- E2-5 implementation pre-gate: initial mypy run **red** on two uninferrable loop lambdas and a variadic keyword dictionary. Replaced them with explicit `functools.partial` factories. The subsequent code gate was green: Ruff passed, mypy checked 32 sources, and 19 tests passed.
- Full tuning run: **green** in 123.002 s. B1 grid = 7 actions and B2 grid = 16 pairs, each on 2,000 train specs; B0-B3 evaluated on 300 val specs with CRN. Train tuning 85.853235 s; validation 35.213939 s.
- Best train settings: B1 action 6 (multiplier 1.30), mean 0.5237723604451462; B2 behind 20% / ahead 5%, mean 0.4022833578587548.
- Validation mean normalised profit: B0 0.4111363131566987; B1 0.5224796738595361; B2 0.39879181105461314; B3 0.5014737710937586. All have zero violations. **Comparator locked to B1** in `params.yaml` and `reports/baselines_val.json`.
- Final E2-5 gate: **green** in 22.388 s. Ruff passed; mypy found no issues in 32 source files; 20 tests passed with 92.71% configured library coverage. The recorded comparator test recomputes the maximum from the validation artifact.
- E2-6 precheck: initial mypy **red** on three calls using a mixed numeric dictionary as variadic keywords. Made all arguments explicit. Ruff and mypy then passed (33 source files), and pre-registration executed successfully.
- E2-6 artifacts: 1,000 test specs (stream 2) and 500 specs per stress prior (streams 3 and 4), all rho-balanced within one episode. Comparator B1; paired bootstrap 2,000 resamples, seed 42, 95% CI; P1 relative lift ≥ 1.0% and CI lower > 0; P2 exactly zero violations; P3 context only.
- Pre-registration SHA-256: `c94f0f97c37afd2788760356b31d89de8fb3d1790b9fc0685bdbcc15bd9cf627`. Test specs: `fb69ba9b96b0224b1d35273d3894f7eaa0351d6c0de4be392ab54f2ff5fb4746`; stress mean −1.5: `cec1622e42ade7081b9b5ec6b8723669805b573814874ef89581ccc3216efb58`; stress mean −3.5: `128bab06ae88f4c28a790102b8c593dde99b479544f3c595d8956932f60a6731`. Splits file SHA-256 in the E2-6 ledger row: `8d2c7bd9608b1f1d4a0e9f1c421044c37307af1b58f1982f1d4b22fc06eec886`.
- Final combined gate: **green** in 24.248 s. `ruff check .` passed; `ruff format --check .` passed (938 files); mypy found no issues in 262 source files; import-linter kept both contracts (245 files, 867 dependencies); 43 shared/project tests passed with 85.35% total coverage. Only the two documented infinite-Box-bound Gymnasium warnings remain. Mypy notes the `sb3_contrib.*` override is unused until E2-7.
- Clean stop verified: no `reports/models/`, `reports/metrics.json`, `reports/test_episodes.json`, or `reports/sealed_access.json`; no PPO training or sealed evaluation; no `/Users/` strings under project 15; no commit, push, or merge. HEAD remains `18adc59d` on `wave7-dynamic-pricing-rl-2026-11-25`.
- Pre-existing untracked `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/` was not read or modified.
