# Wave 7 execution notes: dynamic pricing through release registration

Date: 2026-11-25  
Executor: Kimi Code  
Branch: `wave7-dynamic-pricing-rl-2026-11-25` (from `main` at `18adc59d`)  
Scope: S-0 and E2-1 through E2-6, followed after the owner commit by E2-7 through E2-9 and S-R.

## Protocol

- Execute each step only after the preceding gate is green.
- Keep all work uncommitted for owner and Claude review.
- Read project 02's M5 parquet inputs only; do not evaluate test or stress specs until the committed pre-registration gate and E2-7 are green, then permit exactly one sealed read per set.
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

## Completion phase: E2-7 through S-R

### E2-7 — masked PPO training

- Owner gate verified: HEAD `fc00e61ada82176f12774d610755648167794978` (`feat(15-dynamic-pricing-rl): freeze E2-6 pre-registration and S-0 intervals`). Worktree has no Wave 7 modifications at phase start; the unrelated `opus/` path remains untouched.
- Disk prerequisite: **green**, 77 GiB available (81,128,468 KiB), above the required 25 GiB.
- Initial static check: **red** on four unused/unsorted imports; auto-fixed. Two mypy passes then identified the SB3 factory list's invariance; resolved with the exact `Callable[[], gym.Env[Any, Any]]` contract. Final pre-training gate: Ruff green, mypy green across 35 sources, 25 project tests passed.
- First smoke invocation: **red before learning** because MaskablePPO does not accept PPO's `use_sde` / `sde_sample_freq` keywords. Removed those unsupported keywords; all other defaults remain recorded.
- Successful smoke: 16,384 steps in 21.561371 s; projected 3.290004 h for 3 × 3M steps, within 24 h. Retained 3,000,000 steps per seed.
- Full training: **green**; three 3,000,000-step seeds completed in 11,220.410 s total task wall time. Per-seed training wall clocks: seed 0 3,705.114332 s; seed 1 3,773.055765 s; seed 2 3,695.921757 s. SB3 completed 3,014,656 timesteps per seed because rollouts are quantized to 8 × 2,048 steps.
- Validation means (300 episodes each, action masks passed at every prediction): seed 0 0.5125362780099602; seed 1 0.5143695547914966; seed 2 0.5142881251584195. All three have zero violations. **Selected seed 1**; only `reports/models/ppo_seed_1.zip` remains (445 KiB), and both non-winning checkpoints were deleted.
- Initial full E2-7 gate: Ruff, mypy (264 source files), and import-linter green; pytest **red** after 24 passes because the E2-6 clean-stop test still asserted that `reports/models/` must not exist. Replaced that obsolete phase assertion with a durable check that the E2-6 ledger row predates every E2-7/E2-8 row and that later rows have empty `request_hosts`.
- Final E2-7 gate: **green** in 24.298 s. `ruff check .` passed; mypy found no issues in 264 source files; import-linter kept both contracts; 25 project tests passed with 51% current project coverage (root threshold applies to configured combined coverage, while the run also emitted a non-failing `Module libs was never imported` warning). Only the two documented Gymnasium infinite-Box-bound warnings remain. No sealed evaluation had occurred.

### E2-8 — sealed evaluation preflight (blocked before consumption)

- Added `evaluate.py` with a hard any-prior-`seal_read` guard, frozen spec-count/hash checks, winning-model load and validation-episode preflight, tuned B1/B2 settings from `baselines_val.json`, CRN episode evaluation, fluid UB, code-computed P1/P2 verdicts, and paired bootstrap through `portfolio_eval.intervals` (2,000 resamples, seed 42). Added three fixed-seed test-trace captures inside the single planned pass so no later sealed rerun is needed.
- Development-only evaluator gate, first invocation: **red** at Ruff on one E501 long ledger string; fixed formatting only. Second and third invocations exposed synthetic-test mistakes: an exact floating-point threshold case fell just below 0.01, and a two-row varying-difference bootstrap correctly had a zero lower bound. Changed the test fixtures to a positive-CI passing case and a below-threshold failing case; the production gate formula was not relaxed.
- Final development-only evaluator gate: **green** in 24.009 s. Ruff passed; mypy found no issues in 36 source files; 30 project tests passed. Tests cover P1 pass/fail, P2 failure on any executable-policy violation, permanent rejection of any prior seal read, and 91-step trace capture on a synthetic development episode. No sealed policy evaluation occurred.
- External sealed preflight: **red**. The committed `params.yaml` preregistration block exactly matches the frozen SHA-256, and current `data/splits.json` still matches all three frozen spec hashes. However, `git show fc00e61a:projects/15-dynamic-pricing-rl/data/splits.json` failed because the file is absent from the owner commit. `data/calibration.json` is absent too. Both are excluded by the root `data/` ignore rule (`git status --ignored` reports `!! projects/15-dynamic-pricing-rl/data/`). Thus the handoff requirement that the owner commit `params.yaml`, `data/splits.json`, code, and tests before E2-8 is only partially satisfied.
- Action taken: **stopped before E2-8 execution**. `reports/sealed_access.json`, `reports/metrics.json`, and `reports/test_episodes.json` remain absent; no sealed set was consumed and no metrics stamp was attempted. No commit, push, or merge was made. Owner must force-add and commit the two frozen data artifacts before the sealed read can resume.

### E2-8 — sealed evaluation completed after owner input commit

- Owner resolved the committed-input blocker at `b9d37131b07fa1dbc1eb20f3cab441d0e65ebab4`. Preflight verified that this commit contains byte-identical `data/calibration.json` and `data/splits.json`; the preregistration block still matches `fc00e61a` and its frozen SHA-256. Seed-1 checkpoint and validation reports were reused; E2-7 was not rerun.
- Single `seal-read` invocation: **green**, exit 0, 305.366 s task wall time (302.250918 s recorded in the E2-8 ledger row). Evaluated test, then stress mean −1.5, then stress mean −3.5; 2,000 episodes per policy. No second invocation occurred.
- Access log: exactly three ordered `seal_read` rows, one per frozen set, with the expected spec hashes. `test_episodes.json` is 1.2 MiB, below the 2 MiB git budget, and contains all episode rows plus fixed-seed traces 89, 654, and 773. Each trace has 91 days for B1 and RL.
- Sealed test mean normalised profit: B0 0.41052759407061923; B1 0.5216981845116502; B2 0.39784503531880555; B3 0.5028383950736631; RL 0.5120026323936958; UB 0.5291234796062397. RL fluid-bound share 96.7643%; B1 98.5967%.
- **P1 fail:** RL minus B1 = −0.009695552117954365; relative lift = −1.8584600073%; paired-bootstrap 95% CI [−0.01143722548094719, −0.007997938457781678], 2,000 resamples, seed 42. The entire interval is negative. **P2 pass:** zero violations for B0, B1, B2, B3, and RL on all 1,000 test episodes. P3 remains context only; both stress sets are recorded without gates.
- Added read-only artifact integrity tests for access counts/order/hashes, episode-array sizes, all-zero executable-policy violations, trace completeness, code-derived verdict consistency, and the git size budget. Final E2-8 gate: **green** in 25.245 s. Ruff passed; mypy found no issues in 36 source files; 33 project tests passed. `git grep -c "/Users/" -- projects/15-dynamic-pricing-rl` produced no matches; a separate all-files search also found none.
- `stamp_metrics_meta.py --help` was inspected before use. The stamping command completed over 17 metrics artifacts and reported one stale artifact. Byte snapshots preserved all 16 unrelated metrics artifacts exactly; only project 15 retained its new `_meta`. Its stamp uses HEAD `b9d37131`, current params/lock hashes, seed 42, and `created_at: null` because the new metrics file is not yet committed. The later lineage `--check` is expected to require an owner commit; no commit was made to work around it.

### E2-9 — figures, standalone report, article, and documentation

- Initial figure implementation gate: Ruff identified Unicode/line-length findings; these were corrected with explicit character constants and wrapped lines. A figure test initially expected nine traces; the actual contracted figure has six (three episodes × B1/RL), so the test expectation was corrected. Final pre-generation project run: **36 tests passed**.
- First DVC attempt used the unavailable `--single-stage` option and did not run a stage. The supported safe command `uv run dvc repro --single-item figures` then completed successfully. It generated all four JSON/HTML figure pairs, `dvc.lock`, and `reports/report.html`. Blanket `dvc repro` was never run, and no policy evaluation occurred.
- `ReportBuilder` output inspection: `report.html` is 77,116 bytes and contains four embedded Plotly figures plus explicit `P1: FAIL.` / `P2: PASS.` text. The figure filenames do not appear in the embedded HTML, so presence was verified through the four figure headings and plot bodies instead.
- Figure gates: `check_figure_budget.py` passed with the pre-existing 519 KiB project-03 warning; `check_figure_axes.py` passed across 158 figures with three pre-existing over-wide-window warnings in projects 01 and 10. All project-15 axes use explicit nonclipping ranges; no heatmap is used.
- Completed `README.md`, `DESIGN.md`, `portfolio.yaml`, and eight-section `story.yaml`. Copy states simulator-only results, the Bijmolt et al. (2005) elasticity assumption rather than causal M5 elasticity, and the absence of reference-price and substitution effects. The roadmap has four shipped cards and one next card. The primary result remains negative throughout.
- Initial story lint: one background-section cap error (161 words) and four reading-ease warnings. Shortened and simplified background/objectives/data/EDA/training. Final `lint_story_language.py`: **14 stories, 0 errors, 0 warnings**.
- `check_headline_numbers.py` now derives project 15's `0.5120` RL mean and `-1.86` relative lift from sealed metrics; both real-repo surfaces pass. Its targeted tests initially hit the root coverage fail-under because no imported source was measured; rerun with `--no-cov`: **8 passed**. The full suite supplies the coverage gate separately.

### S-R — registrations and release gates

- Restored `portfolio.yaml` and `story.yaml`; registered card does/achieves copy and exactly four non-framework tags; updated About counts to 14/fourteen; added root README and docs index rows; added `docs/projects/15-dynamic-pricing-rl.md`; linked project 15 from the M5 data card; added CI/nightly matrix rows with `--cov=src`; registered all four docs figure exports.
- Generators completed: static registry has 14 projects and 2 demos; short-copy map has 14 stories; route manifest has 28 routes including `/projects/15-dynamic-pricing-rl`; all four project-15 PNGs were exported. The export script also rewrote unrelated PNGs that had been clean before the run; those unrelated files were restored byte-for-byte from HEAD, leaving only the new project-15 image directory.
- First short-copy check was red because the root README/docs index rows paraphrased `short_version`. Both now contain the exact generated string. Final check: **42 surfaces across 14 stories, single-sourced**. `check_docs.py` and `check_demo_contract.py` passed. All three generator `--check` commands passed. `mkdocs build --strict` passed; its nav notices and Material for MkDocs notice are informational.
- Full static gate after targeted formatting: Ruff passed; all 949 files are formatted; mypy passed across 266 source files; import-linter kept both contracts (249 files, 891 dependencies).
- First web run: 752 passed, 2 failed because snapshot fallback tests still expected 13 cards. Updated only those expectations/comments to 14. Final web gate: **56 files / 754 tests passed**, ESLint passed, TypeScript and Vite production build passed (962 modules). The existing large-chunk warning remains non-failing.
- Project coverage gate: **36 tests passed**, 52% project coverage; the root configured 80% combined gate does not fail this project-only run. Only the two documented Gymnasium infinite-Box-bound warnings and the non-failing `Module libs was never imported` coverage warning remain.
- API registration: port 8000 was already occupied, so no existing process was touched. A temporary API on port 8015 returned 14 projects and the complete `15-dynamic-pricing-rl` card; it was then stopped. No development server was left running by this work.
- Sealed hygiene recheck: exactly three ordered `seal_read` entries with the frozen test/stress hashes; `test_episodes.json` is 1,297,936 bytes; only `ppo_seed_1.zip` remains; no `/Users/` strings under project 15. No E2-7 or E2-8 execution was repeated.
- `check_release_artifacts.py` remains red on pre-existing non-object `_meta` in projects 02 and 09; project 15 has no release-artifact error. `stamp_metrics_meta.py --check` remains red for unrelated stale artifacts 01, 02, 09, and 11, and for project 15 because its new metrics payload did not exist at stamped HEAD `b9d37131`. Owner review/commit is required before restamping project 15. No unrelated metrics were changed and no commit was made to force this gate green.
- Full offline `HF_HUB_OFFLINE=1 uv run pytest -q` completed in 742.419 s: **red with two failures**, both outside project 15. Project 02 `test_ensemble_composition_quotes_match_committed_metrics` cannot find the committed ensemble member/weight quote in the concurrently rewritten story. Project 10 `test_multi_arm_read_block_shape_references_and_bounds` expects `qini_per_arm_figure` x values `['mens', 'womens']` but the concurrently modified figure supplies numeric values. Combined configured library coverage passed at 97.14%. Per scope, neither unrelated project was edited to repair these failures.
- Final artifact audit verified seed 1, code-derived P1/P2/P3 verdicts, zero executable-policy violations, headline strings in README/story, and all JSON/HTML/PNG figures. A first auxiliary audit invocation used a duplicated project-relative path and failed before assertions; the corrected invocation printed `sealed_copy_and_artifact_audit=OK`. Read-only `dvc status` showed the figures dependency changed after Ruff formatting, along with widespread unrelated pre-existing pipeline drift.
- Final `dvc repro --single-item figures` refreshed only presentation artifacts and `dvc.lock`; it did not invoke sealed evaluation. Final project rerun: **36 passed**, 52% coverage, same two Gymnasium warnings. Final `git diff --check` passed; HEAD and branch remain unchanged.
