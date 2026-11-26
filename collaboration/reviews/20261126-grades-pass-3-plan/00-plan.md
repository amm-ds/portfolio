# Grades pass 3: plan to close the remaining gaps

Date: 2026-11-26 · Author: Claude (review/design lane) · Base: `main` at `acf6f9f7`, plus the uncommitted pass-2 edits (64 paths in `git status`).
Inputs:
- `collaboration/reviews/20261126-post-deploy-grades/00-grades.md`, the original grades.
- `collaboration/reviews/20261126-grades-pass-2/00-pass.md`, what pass 2 did and its §5 "NOT REACHABLE WITHOUT EXPERIMENTS".

This is a plan only. No repo file was edited and nothing was mutated in git. No experiment, training, refit, benchmark or hosted call was run. Every command used was read-only: `git show`/`log`, `stamp_metrics_meta.py --check`, `check_release_artifacts.py`, `gh run list/view`, a `gh api` read of the public NAB repo, and JSON/parquet reads.

## 0. Facts found in this pass that change the plan

1. **CI on `main` has been red since at least 2026-11-24** (last green: `d6aef968`). In the `acf6f9f7` run (`45843100617`), two steps fail:
   - The `gate` job fails at **Release-artifact contract**, before it reaches the stamp check. The errors are `02 …/reports_m5_full/metrics.json: _meta is not an object` and the same for `09 …/reports/metrics.json`.
   - **a11y-axe** reports 4 serious `scrollable-region-focusable` violations, on `/projects/09-agentic-workflows` and `/apps/document-intelligence`, mobile viewport, dark and light.
2. **Why `stamp_metrics_meta.py --check` fails** (`uv run python scripts/stamp_metrics_meta.py --check`: 5 stale, 2 invalid, 17 artifacts):

   | File | Cause | Number change? |
   |---|---|---|
   | 02 `reports_m5_full/metrics.json` | `_meta` deleted in `4798bb68` (the M5 0.6211 sync) | Yes, in that past commit. Stamping now only records lineage |
   | 09 `reports/metrics.json` | `_meta` deleted in `390c1415` | No new numbers from stamping |
   | 01 `reports/metrics.json` | Stamped at `a879fb51`. `390c1415` then added `ragas_version`, `judge_model` | No. Additive keys only (diffed) |
   | 11 `reports/metrics.json` | Stamped at `a879fb51`. `390c1415` then added `time_min_s`/`time_max_s` per cell | No. Additive keys only (diffed) |
   | 12 `reports/metrics.json` | The pass-2 copy edit to `validation_tie_interval.interpretation` | No. A string only |

   The stamper has **no per-file option**. It rewrites all 17 files with `git_sha = HEAD` and `sort_keys`. The lineage rule requires the stamped sha to hold an identical payload, so the stamp has to go in **its own commit after the content commit**, as in `07be7998`.
3. **The 10 `qini_per_arm` "4.4× window" is mostly a gate false positive.**
   - `check_figure_axes.py` measures only the marker x values (3.37 and 12.03, a span of 8.66).
   - The figure draws `error_x` bars from −6.78 to 24.21 (a span of 31.0) inside a window of [−9.78, 28.21] (38.0). Against what is actually drawn, that is 1.23×.
   - The figure is built from committed `metrics.json` → `multi_arm.per_arm`, so it can be rebuilt **without re-running the bootstrap**.
   - The real visual weakness is the title, "Per-arm AUUC on randomized arm vs control pairs", which states no finding.
4. **The 02 blend curve cannot be recomputed by arithmetic.**
   - `catalog_forecasts.parquet` holds per-member columns, but they come from the earlier run. Its member test WRMSSE (storecat 0.6575, store 0.6217, dept 0.6313) differs from the current run (0.6225, 0.6219, 0.6459).
   - Applying the final weights (0.95/0.00/0.05) to those columns would draw a curve that never scored 0.6211.
   - The choices are: drop or move the figure, or run a targeted refit.
5. **The `_meta` clobber is not unique to 10.** Generators in 01, 02, 04, 05, 07 and 10 read or write analysis blocks under `metrics["_meta"]`, and 12's report generator reads `_meta.champion/ci`. The provenance stamp replaces that key.
   - Any Phase 1 or Phase 2 re-run of those stages will write analysis into `_meta`, and the stamp will destroy it again.
   - `10 demo_payload.py:178` reads `metrics["_meta"]["cost_model"]`, which no longer exists, so `demo-payload` would raise `KeyError` at HEAD.
6. **NAB is MIT-licensed** (GitHub API: `numenta/NAB`, license MIT, not archived, last push 2024-12-03). Vendoring the scorer into this MIT repo has no licence blocker.
7. **The 04 cascade gain is one row.** Fresh accuracy goes from 0.953 to 0.954 on 1,000 rows, with 22 reviews. A paired interval will almost surely include zero. The value of the re-run is the persisted per-row evidence and an honest interval, not a better number.
8. **The 01 judge cost has a measured basis.** In `final_v3_e2e/metrics.json` → `detail.final_v3.meter.judge`: 232 calls, 341,385 input and 25,859 output tokens, $0.444 on the current judge.

## 1. Grade ceiling: honest summary

The scores below are after pass 2, as `C/R/T/V → overall`. The target is overall ≥ 9.0 with no axis below 8.

- The gaps in this plan only move **Technologies** and **Visualizations**. Every project except 06, 07, 11 and 15 has Contents at 8.
- So even if every gap below closes, most projects land at **8.3–8.5**, not 9.0.
- Reaching 9.0 also needs Contents 9 (copy work, not compute). This plan does not cover that; see §7.

| # | Now | After P0 | After P1 | After P2 | After P3 | Best honest ceiling from this list |
|---|---|---|---|---|---|---|
| 01 | 8/9/8/8 8.3 | same | same | 8/9/9/8 8.5 (if the judges agree) | same | 8.5 |
| 02 | 8/9/8/7 8.0 | 8/9/8/8 8.3 (figure moved or dropped) | same | same | 8/9/8/9 8.5 (refit) | 8.5 |
| 03 | 8/9/8/8 8.3 | same | 8/9/9/8 8.5 (NAB scorer) | same | same | 8.5 |
| 04 | 7/9/8/8 8.0 | 8/9/8/8 8.3 (glossary asides cut) | same | 8/9/9/8 8.5 | same | 8.5 |
| 08 | 8/9/6/8 7.8 | same | same | same | 8/9/8/8 8.3; T9 → 8.5 needs a second host | 8.3–8.5 |
| 09 | 8/9/8/8 8.3 | same | same | 8/9/9/8 8.5 (if the repeats pass) | same | 8.5 |
| 10 | 8/9/8/7 8.0 | 8/9/8/8 8.3 | 8/9/9/8 8.5 | same | same | 8.5 |
| 12 | 8/9/7/8 8.0 | same | 8/9/8/8 8.3 (sensitivity arm) | same | 8/9/9/8 8.5 only if the headline is replaced | 8.3 (or 8.5 with a new headline) |
| 15 | 9/10/9/8 9.0 | 9/10/9/9 9.3 (after a browser check of the diagrams) | | | | 9.3 |

**12 cannot reach T9 without changing a headline number.** The pruning and lag defects live in the committed run, so fixing them moves MLP 25.4316, LightGBM 25.3732 and the CIs. It also breaks 13's reproduction gate, which is keyed to 25.43163. The honest choice is probably to stay at T8: run the fix as a disclosed sensitivity arm, keep the headline, and say in the article "a corrected-pruning, date-aware-lag variant scores X [CI]; the headline keeps the committed run."

**08 cannot reach T9 on one machine.** The honest choice may be to accept T8 and write "single host; cross-host behaviour untested."

## 2. Ranking by value per cost

| Rank | Item | Phase | Moves | Cost |
|---|---|---|---|---|
| 1 | Commit pass 2 on the right branch, restamp 01/02/09/11/12, fix the axe violations, get CI green, redeploy | 0 | Unblocks everything; makes pass 2 live | 0 compute |
| 2 | 10: count error bars in the axes gate, retitle `qini_per_arm`, rebuild from committed `per_arm` | 0 | 10 V 7→8 | 0 compute |
| 3 | Wire `check_diagram_fences.py` into CI | 0 | Protects 15 V; stops a repeat of the 15 regression | 0 |
| 4 | 02: move `m5_full_sample_series` to the demo section, or drop it | 0 | 02 V 7→8 | 0 |
| 5 | 15: browser check of the 5 diagrams after redeploy | 0 | 15 V 8→9 | 0 |
| 6 | 01/09: cut short-version jargon on the 4 single-sourced surfaces | 0 | Reader-facing C; keeps 01/09 C at 8 safely | 0 |
| 7 | 04: cut the glossary asides | 0 | 04 C 7→8 | 0 |
| 8 | Move generators off `_meta` (01/02/04/05/07/10, plus readers in 10 and 12) | 1 (prerequisite) | Makes every later re-run safe | CPU seconds (tests) |
| 9 | 10: re-run `cli evaluate` to persist the CIs | 1 | 10 T 8→9 | CPU minutes |
| 10 | 04: re-run the cascade with per-row decisions | 2 | 04 T 8→9 | ≈ $0.03 hosted |
| 11 | 09: 5 repeated live held-out runs | 2 | 09 T 8→9 | ≈ $0.5–0.9 hosted |
| 12 | 01: second-family re-grade of the committed final_v3 answers | 2 | 01 T 8→9 (conditional) | ≈ $1–2 hosted |
| 13 | 12: sensitivity arm (fixed pruning, date-aware lags) | 1 | 12 T 7→8 | CPU ~1 min |
| 14 | 03: vendor the NAB scorer and rescore | 1 | 03 T 8→9 | CPU minutes plus ~a day of engineering |
| 15 | 08: harder quality eval and a quantization-matched pair | 3 | 08 T 6→8 | hours of local inference per arm set |
| 16 | 02: targeted refit of the two non-zero members at the test origin | 3 | 02 V 8→9 | ≈ 9 CPU-hours summed (estimate) |
| 17 | 01: fresh sealed `final_v4` with a cross-family judge | 3 | 01 T stays 9, new headline | ≈ $3 hosted plus owner hours to author and label |
| 18 | 08: second machine | 3 | 08 T 8→9 | hardware access |
| 19 | 12: replace the headline and rebuild 13 | 3 | 12 T 8→9 | CPU minutes plus a full 13 re-derivation; every 12/13 number moves |

## 3. Phase 0: no compute, mechanical

**Owner approves before start:**
- (a) which branch to commit on;
- (b) whether the restamp keeps all 17 rewritten files or only the 5 stale ones;
- (c) the replacement short-version wording for 01 and 09;
- (d) drop or move the 02 figure;
- (e) touching app code for the axe fix;
- (f) the CI workflow edit.

### P0.1 Branch, commit, restamp, CI green, redeploy
- **Target.** CI green on `main`. Production `/health` sha = new HEAD. Pass-2 grades become live.
- **Branch.**
  - `wave8-articles-truthfulness-2026-11-25` exists locally and on `origin`, and its tip is `acf6f9f7`, the same commit as `main`.
  - `git switch wave8-articles-truthfulness-2026-11-25` therefore carries the 64 uncommitted paths with no conflict.
  - Commit there, then merge to `main` by the owner's usual route. Committing directly on `main` is the alternative, if the owner prefers.
  - Commit messages carry no model co-author trailer (owner rule).
- **Steps.**
  1. Commit the pass-2 content (split by project as the repo's commit convention prefers).
  2. Run `uv run python scripts/stamp_metrics_meta.py` from that commit. Then either keep only the 01, 02, 09, 11 and 12 rewrites (`git restore` the other 12), or keep all 17. All 17 is harmless for lineage but noisier in the diff. **Recommendation: keep 5.** Commit as `chore(metrics): restamp _meta lineage for 01 02 09 11 12`.
  3. Axe fix: find the horizontally scrollable container that renders on the 09 project page and on `/apps/document-intelligence` at mobile width (likely a table or code wrapper under `apps/showcase-web/src/`). Give it `tabIndex={0}` plus an accessible name (`role="region"`, `aria-label`). This is app code, so it is an owner-assigned implementation.
  4. Push, wait for CI, redeploy, and check `/health`. The live 13 story should have 0 "champion" hits.
- **Files.** The pass-2 set; `projects/{01,02,09,11,12}/…/metrics.json` (stamp only); one or two showcase-web components.
- **Cost.** None.
- **Risk to headlines.** None. The diffs above show the stamp changes `_meta` only. 02's payload change happened in `4798bb68`; the stamp records it without hiding it.
- **Risk to committed evidence.** Low. Check that the stamp commit touches only `_meta` (`git diff --stat`, then a JSON payload diff excluding `_meta`).
- **Verification.**
  - `stamp_metrics_meta.py --check` exits 0.
  - `check_release_artifacts.py` exits 0.
  - `check_headline_numbers.py` exits 0 (14 claims).
  - `node scripts/axe_check.mjs` locally, or the a11y-axe CI job, shows 0 violations.
  - The `ci` workflow is green on `main`.
  - `/health` sha = HEAD.

### P0.2 Wire `check_diagram_fences.py` into CI
- **Target.** Protects 15 V 9 and every story's fences.
- **Steps.**
  - Add a step to `.github/workflows/ci.yml` in the `gate` job, right after "Story language lint" (line ~118):
    ```yaml
          - name: Diagram fence resolution
            # Every ```diagram id in projects/*/story.yaml must resolve in
            # apps/showcase-web/src/diagrams/{index,auto/index}.ts (15 shipped fallbacks).
            if: needs.changes.outputs.python == 'true' || needs.changes.outputs.web == 'true'
            run: uv run python scripts/check_diagram_fences.py
    ```
  - Run `scripts/lint_ci.py` if it validates workflow structure. Check whether the `scripts/tests` pytest step already collects `test_check_diagram_fences.py`; it should.
  - Optionally add a `Makefile` target, to match `lint-story`.
- **Files.** `.github/workflows/ci.yml`, and optionally `Makefile`.
- **Cost.** About 1 s of CI time.
- **Risk.** None.
- **Verification.**
  - The step appears and passes in the CI run.
  - Local negative test: temporarily rename one fence id. The script exits 1. Revert.

### P0.3 01 and 09 short-version jargon
- **Target.** Reader-facing Contents. This keeps 01 and 09 at C8 and removes the grader's "insider tags" note. It does not lift either project to C9 on its own.
- **Steps.** The short copy is single-sourced and checked, not generated. Edit all four surfaces identically:
  1. `projects/<id>/story.yaml` `short_version`;
  2. the root `README.md` Projects row ("Highlights" cell);
  3. `docs/projects/index.md`;
  4. the opening blockquote of `docs/projects/<id>.md`.

  Then run `scripts/gen_story_short.py` and `scripts/gen_static_registry.py`.
  - The README "Stack:" text is hand-written. Drop `final_v3`, `judge_v2`, "S3", "owner-labelled", "live-grader" and "h19 … calculator guard" there too.
  - The headline gate needs `0.9091` and `0.946` on README and story for 01, and `15/15` and `13/13` for 09. Keep those tokens.
- **Draft wording, for owner approval.**
  - 01: "Cited question answering over 593 Wikipedia articles. Hybrid retrieval puts a correct passage in the top five 94.6% of the time (recall@5 0.946). On a final 120-question test: F1 0.9091, precision 0.952, faithfulness 0.872, one unsupported answer. The automatic judge agreed with all 30 hand-labelled checks."
  - 09: "Plan-act-review workflow with typed outcomes and deadlines. Recorded runs: 15/15 fixed tasks, 13/13 unseen answers, 5/6 correct refusals. A live re-run with hosted models: 13/13 answers, 6/6 refusals, all 19 tasks within budget; the one refusal came from a calculator safety check."
- **Files.** The 4 surfaces × 2 projects; `apps/showcase-web/src/lib/storyShort.ts` and `staticRegistry.ts` (generated).
- **Cost.** None.
- **Risk.** None to numbers.
- **Verification.**
  - `check_short_copy.py --check`, `gen_story_short.py --check`, `gen_static_registry.py --check`, `check_headline_numbers.py`, `lint_story_language.py` and `mkdocs build --strict` all exit 0.

### P0.4 10 Visualizations: axes gate and `qini_per_arm` title
- **Target.** 10 V 7→8.
- **Steps.**
  1. `scripts/check_figure_axes.py`: include `error_x.array`/`arrayminus` and `error_y` extents (point ± error) in the data span. Add a test in `scripts/tests/` with a forest plot whose window fits its error bars.
  2. `projects/10-uplift-experimentation/src/uplift_experimentation/evaluate.py:qini_per_arm_figure`:
     - Retitle with the finding, for example "Neither arm's AUUC interval excludes zero".
     - Optionally tighten the padding from `-3/+4` to about 5% of the CI span.
  3. Rebuild only `reports/figures/qini_per_arm.{json,html}` by calling `qini_per_arm_figure(metrics["multi_arm"]["per_arm"])` on committed values. This is the pass-2 pattern for 12 `bootstrap_ci`; there is no bootstrap re-run.
  4. In `report.html`, replace the title string only.
- **Files.** `scripts/check_figure_axes.py`, its test, `evaluate.py`, `reports/figures/qini_per_arm.{json,html}`, `reports/report.html`.
- **Cost.** None.
- **Risk.** None to numbers. JSON `data` stays byte-equal.
- **Verification.**
  - `check_figure_axes.py` passes with 2 warnings (both `01 retrieval_ladder`), not 3.
  - The `qini_per_arm.json` data diff is empty.
  - The headline gate passes.

### P0.5 02 Visualizations: `m5_full_sample_series` (owner decision)
- **Target.** 02 V 7→8. V 9 needs P3.2.
- **Option A (recommended): move.**
  - Move the figure out of the results section into the demo section of `story.yaml`.
  - Re-caption it as "what the demo serves: the earlier 0.6161 blend". Keep "not the scored 0.6211 blend" in the title, and shorten the ~100-word caption.
  - Make the hard-coded takeaway strings in `m5_full_figures.py` ("0.6161 (weights 0.60/0.10/0.30)", "under 0.001") read from the parquet schema metadata (`ensemble.weights`) and `metrics.json`. Rebuild offline through `build-figures-m5-full`.
- **Option B: drop** the figure from `story.yaml` (figures list and caption). The JSON can stay committed or be deleted.
- **Files.** `projects/02-demand-forecasting/story.yaml`, `src/demand_forecasting/m5_full_figures.py`, `reports_m5_full/figures/m5_full_sample_series.*`; `docs/projects/02-*.md` if it embeds the figure.
- **Cost.** None. The figure builder reads committed artifacts only.
- **Risk.** None to numbers.
- **Verification.**
  - Gates: `lint_story_language`, `check_demo_contract`, `check_figure_axes`, `gen_static_registry --check` and `check_headline_numbers`.
  - Visual check in the app.

### P0.6 Other no-compute items carried from pass 2
- 15: browser check of the 5 diagrams on the redeployed page. No "Unknown diagram spec." text, 5 flows rendered. Moves 15 V to 9.
- 04: cut the glossary asides in `story.yaml` (C 7→8).
- 01: change the figure titles "65 golden questions" to "65 tuning questions" through `src/rag_agent/figures.py`, rebuilt from committed data.
- 03: change the `telemetry_flags` title "Champion flags" to "Served-model flags".
- 08: the owner reads the MLX build's recorded quantization on the bench host, either with `ollama show gemma4:31b-mlx` or from the MLX `config.json` `quantization` block. This is a metadata read, not a benchmark.
  - If found, commit it as `projects/08-inference-serving/reports/model_provenance.json` and replace "unrecorded quantization".
  - This is a prerequisite for P3.1(b).

## 4. Phase 1: cheap compute (CPU minutes)

**Owner approves before start:**
- (a) the `_meta` generator refactor (P1.0) as a code change;
- (b) for each re-run, that committed `metrics.json`, `report.html` and figures may be rewritten, given the stated byte-equality checks;
- (c) for 03, adding a vendored dependency and publishing a new NAB score;
- (d) for 12, "sensitivity arm, headline kept" (recommended) versus "replace headline" (moves to P3.4).

**Stop rule for every Phase 1 run.** If any committed headline value changes beyond the stated tolerance, stop. Do not commit, and report back.

### P1.0 Prerequisite: move analysis out of `_meta`
- **Steps.**
  - In `01 rag_agent/reporting.py`, `02 demand_forecasting/evaluate.py`, `04 nlp_classification/evaluate.py`, `05 churn_pipeline/{cli,demo_payload}.py`, `07 mobility/evaluate.py` and `10 uplift_experimentation/{evaluate,demo_payload}.py`: write the analysis under a top-level `analysis` key, and read it from there.
  - Do the same for 12's report generator, which reads `_meta.champion/ci`.
  - `_meta` stays reserved for the provenance stamp.
  - Add a unit test per project, plus a repo test asserting that no `src/` writes `["_meta"][...]` other than the stamper.
- **Cost.** Tests only. **Risk.** None to committed artifacts until a stage is re-run.
- **Verification.** Per-project pytest, `mypy`, `ruff`, and `grep -rn '\["_meta"\]' projects/*/src` returning nothing.

### P1.1 10 Technologies: persist the paired CIs
- **Target.** 10 T 8→9.
- **Steps.**
  1. After P1.0, run `uv run python -m uplift_experimentation.cli evaluate`. It is a deterministic 1,000-rep paired row bootstrap with seed 1041.
  2. Check `analysis.ci.t_learner_vs_random.profit_at_budget_diff_ci` against the history value at `0c01c45d` (`[717.58, 4766.66]`) and the `report.html` values (+$718/+$4,767, −$13,125/−$5,808).
  3. Point the `_m10` gate in `check_headline_numbers.py` at `metrics.json` as well as `report.html`.
  4. Restamp in its own commit.
  5. Fix `demo_payload.py`, then decide whether to regenerate or delete the orphan `reports/demo_payload.json`.
- **Cost.** CPU minutes (one bootstrap). **Basis:** pass 2 §5.
- **Risk to headlines.**
  - Low if the run is bit-deterministic.
  - Medium if library versions drifted since the committed run. Every point metric must stay byte-equal (diff the payload outside `analysis`/`_meta`).
- **Risk to evidence.** `report.html` and figures get rewritten (random div ids). Restore any file whose data is unchanged, following pass-2 practice.
- **Verification.**
  - The payload diff outside `analysis` is empty.
  - The CIs match `0c01c45d` to 1e-6.
  - The gate passes with the CI read from `metrics.json`.
  - `stamp --check` exits 0.

### P1.2 12 Technologies: sensitivity arm for the pruning and lag defects
- **Target.** 12 T 7→8, with the headline kept.
- **Steps.**
  1. Prove the pipeline reproduces first: re-derive the committed MLP 25.4316 from the committed recipe. 13's reproduction gate already does this; reuse it.
  2. Add a variant config with:
     - a pruning rule that keeps the higher-MI member of a correlated pair (keeps `atemp`);
     - date-aware lags: join on timestamp minus h, with NaN for missing hours, instead of positional shifts.
  3. Train and evaluate the variant. Recorded cost: train 44.4 s, evaluate 13.3 s.
  4. Write `reports/sensitivity_pruning_lags.json`: variant MAE per model, and the block-bootstrap CI of the delta against the committed run.
  5. Add one figure or table row and one article paragraph.
- **Files.** `projects/12-tabular-ml-lifecycle/{params.yaml or a new params_variant.yaml, src/…/stages.py, reports/sensitivity_pruning_lags.json, story.yaml, README.md}`, `docs/projects/12-*.md`.
- **Cost.** About 1 CPU minute.
- **Risk to headlines.** None if the variant stays a separate artifact. **Do not overwrite `metrics.json`.**
- **Risk to evidence.** None. 13 is untouched.
- **Honest note.** If the variant beats the committed model by more than its CI, the article must say so plainly: "the committed headline carries a known defect worth X MAE".
- **Verification.**
  - The reproduction of 25.4316 passes first.
  - The variant JSON is committed and gated in `check_headline_numbers.py` as a secondary claim.
  - `metrics.json` is byte-unchanged.

### P1.3 03 Technologies: official NAB score
- **Target.** 03 T 8→9.
- **Steps.**
  1. Vendor the NAB scorer at a pinned commit of `numenta/NAB` (MIT), with its `config/profiles.json` (standard, reward_low_FP_rate, reward_low_FN_rate) and `labels/combined_windows.json`. Put it under `projects/03-anomaly-detection/vendor/nab/` with its LICENSE, or pin it as a git dependency in `pyproject.toml` + `uv.lock`.
  2. Check that the committed detectors emit per-timestamp scores. Pass 2 shows `cli evaluate` scores the saved models without training, so the scores can be produced.
  3. Run NAB's threshold optimisation and scoring on the **NAB series only**. Exclude the synthetic injected window.
  4. Write `reports/nab_official_score.json` (three profiles, plus the NAB null and perfect baselines from the scorer).
  5. Replace "NAB score not reported" in story, README and docs with the score, its profile, and a pointer to NAB's own published scoreboard as the comparator. Quote no leaderboard number that was not read from the vendored repo.
- **Cost.** CPU minutes, plus about a day of engineering, because NAB's code is old and may need a Python 3 adapter. The new dependency affects `uv.lock` and therefore every stamp's `uv_lock_sha256`, so restamp all 17.
- **Risk to headlines.** The existing 1,609 alerts, 0.527 and [0.230, 0.811] stay. A new public number is added, and it may compare poorly with NAB's top entries; that is the honest outcome.
- **Owner decision.** Whether to publish it either way.
- **Verification.**
  - The scorer's own unit tests pass on its sample data.
  - The null and perfect baselines score 0 and 100 under the standard profile.
  - The new JSON is gated in `check_headline_numbers.py`.

## 5. Phase 2: hosted calls (stated budget)

**Proposed budget cap: $5.00 total across Phase 2**, metered by each project's existing per-phase cost meter. Estimated spend is ≈ $2–3.

**Owner approves before start:**
- (a) the budget cap;
- (b) the provider and model for the 01 second-family judge;
- (c) for each item, whether a re-run that disagrees with the committed number **replaces** it or is published **beside** it as a replication. Recommendation: beside it, always.
- (d) for 01, that a judge-agreement read of the consumed `final_v3` answers is acceptable and will be disclosed as a fifth read that does no selection.

**Stop rule.** If the meter passes 150% of an item's estimate, stop that item and report.

### P2.1 04 Technologies: cascade re-run with per-row decisions
- **Target.** 04 T 8→9. R stays 9.
- **Steps.**
  1. Change `llm-cascade` to persist one row per example: id, split, baseline prediction, confidence, routed y/n, LLM verdict, final prediction, gold.
  2. Run `dvc repro llm_cascade` (the stage is manual by design, `dvc.yaml:102`). The DistilBERT weights are on disk (`reports/models/`, 2.2 GB), so baseline inference is local CPU.
  3. Compute a paired bootstrap CI and a McNemar test of cascade versus baseline macro-F1 and accuracy on the fresh holdout.
  4. Write `reports/llm_cascade_rows_<date>.jsonl` and `reports/llm_cascade_paired_ci.json`.
- **Cost.** ≈ $0.024 hosted. **Basis:** `llm_cascade.json` `ops`: 9,807 input and 3,466 output tokens, `est_cost_usd` 0.023671, 44 reviews. Cap: $0.10.
- **Risk to headlines.** The LLM verdicts are not bit-reproducible, so the re-run cascade F1 may differ from 0.95393.
  - Publish it as a replication beside the committed number, and gate both.
  - The expected interval includes zero, which matches the article's "gain not measurable".
- **Verification.**
  - The rows file reconciles to the summary counts (n_reviews, F1).
  - The CI file is gated.
  - The committed `llm_cascade.json` is unchanged, unless the owner chose to replace it.

### P2.2 09 Technologies: repeated live held-out runs
- **Target.** 09 T 8→9, if the repeats hold.
- **Steps.**
  1. Run the 19-task live held-out suite 5×, with the same config as `reports/live_confirmation_20261119/`.
  2. Write `reports/live_repeats_<date>/` with per-run grading files, per-task pass^5 / pass@5, and p50/p95 latency across runs.
  3. Add one sentence and one table to the story.
- **Cost.** ≈ $0.47 at pass 2's $0.094 per 19-task run. If the committed $0.00876/task applies to this suite, it is ≈ $0.83. The two sources disagree, so budget $1.00 and record the meter.
- **Risk to headlines.** If any run fails a task, the "19/19" line must become "19/19 on the first run; pass^5 = k/19". That is more honest and still a T9.
  - The committed `live_confirmation_20261119/` stays untouched.
- **Verification.**
  - Each run's grading file reconciles to the summary.
  - A headline-gate entry covers pass^5.
  - `lint_story_language` passes.

### P2.3 01 Technologies: second-family judge
- **Target.** 01 T 8→9, if inter-judge agreement is high. If it is low, R may drop from 9 to 8, and the article must say so.
- **Steps (tier a, recommended now).**
  1. Calibrate a judge from a different model family on the existing 30 owner-labelled sample (`judge_calibration_v2`).
  2. Re-grade the committed `final_v3` answers. These are fixed outputs, and nothing is selected or tuned.
  3. Report Cohen's κ / % agreement against the current judge, and the F1/faithfulness under each judge.
  4. Write `reports/cross_family_judge_<date>/`.
- **Cost.** Basis: judge phase 341,385 input and 25,859 output tokens (232 calls).
  - Sonnet 5.5 ($2/$10 per MTok): 0.68 + 0.26 ≈ **$0.94**.
  - Opus 5.5 ($4/$20): ≈ **$1.88**.
  - Calibration on 30 items: about $0.15.
  - Prices are from the Anthropic pricing table cached 2026-11-03.
  - Cap: $2.50.
- **Risk to headlines.** None if published beside the headline. Low agreement weakens the 0.9091 claim, and that has to be stated.
- **Verification.**
  - The agreement JSON is committed and the meter recorded.
  - `final_v3_file_access.json` gains one logged read, labelled "judge-agreement, no selection".
- Tier b (fresh sealed `final_v4`) is P3.3.

## 6. Phase 3: new experiments or hardware

**Owner approves before start:**
- (a) hardware access and electricity time for 08;
- (b) about 9 summed CPU-hours for 02;
- (c) owner hours to author and label `final_v4`;
- (d) for P3.4, explicit acceptance that every 12 and 13 headline number moves.

### P3.1 08 Technologies: from T6 toward T8 (T9 needs a second host)
- **Steps.**
  - (a) A harder quality eval per arm, replacing the saturated smoke check. Use a fixed public subset with exact-match grading, for example a few hundred items of a reasoning or QA set with a permissive licence. Pin item ids, seed and prompt.
  - (b) A quantization-matched cross-runner pair, for example MLX 4-bit against GGUF Q4_K_M, or MLX 8-bit against Q8_0, of the same `gemma4:31b`. Record the quantization in the artifact (see P0.6).
  - (c) A second machine of a different class, with the same harness.
  - Add each result as new cells and keep the existing cells (67.73 tok/s and so on).
- **Cost.** Hours of local inference per arm set (electricity only). **Basis:** pass 2 §5. (c) needs access to other hardware.
- **Risk to headlines.** The speed cells stay. The "serving choice" conclusion can flip if quality differs, and the article must follow the evidence.
- **Verification.**
  - New `reports/quality_eval.json` and `reports/quant_pair.json`, gated.
  - `engine_panel` subtitle and captions re-checked.
  - The 08 DESIGN.md lists the second host (only with c).
- **Honest note.** Without (c), say "single host" and accept T8.

### P3.2 02 Visualizations: targeted refit for the final-blend curve
- **Steps.**
  1. Refit only `lgbm_pool_storecat` (weight 0.95) and `lgbm_pool_dept` (0.05) at the test origin, 2016-05-22, with the current run's config.
  2. **Before using any curve**, check that their test WRMSSE reproduces the committed 0.62252 / 0.64586, and that the blend reproduces 0.62105, to 1e-6. If not, abort.
  3. Rebuild `catalog_forecasts.parquet`, the demo payload, and `m5_full_sample_series`.
- **Cost.** ≈ 1/10 of the origins × 2/8 of the candidates × 1,348,530.6 s summed ≈ **33,700 s ≈ 9.4 summed CPU-hours**.
  - This is a rough estimate. It assumes uniform cost per candidate-origin; pooled-store fits may cost more.
  - It also needs the 1.5 GB-class M5 raw data on disk.
- **Risk to headlines.** None if reproduction passes. The demo changes from the 0.6161 blend to 0.6211, so `check_demo_contract.py` and the demo copy must change too.
- **Verification.**
  - The reproduction check is logged into `evaluation_metadata.json`.
  - The demo contract passes.
  - The caption drops "earlier blend".

### P3.3 01: fresh sealed `final_v4` with a cross-family judge
- **Steps.**
  - The owner authors and seals 120 new questions with gold answers, plus a hash file.
  - Run the full pipeline once, graded by both judges.
- **Cost.** Agent + verify ≈ $1.01 at the committed rates (0.781 + 0.233). Two judges ≈ $0.44 + $0.94. Total ≈ **$3**, plus several owner hours.
- **Risk.** A new headline replaces 0.9091. That is the point of the step, and it must be decided beforehand.

### P3.4 12: replace the headline (only if the owner wants T9)
- Retrain on the corrected pipeline, then re-derive everything downstream in 13: reproduction gate target, ONNX export and parity, Docker images, serving latencies, 13 copy and diagrams.
- Every 12 and 13 number moves.
- **Recommendation: do not do this in pass 3.** Keep P1.2 and accept 12 T8.

## 7. What this plan does not reach

- An overall of **9.0** for 01–13 also needs Contents 9 and, for most projects, Visualizations 9: plainer, shorter copy, and finding-titles on every figure.
- That is a separate copy and figure pass. It costs no compute but takes editorial time, and it is not in this list.
- Without it, the honest portfolio statement is: "15 at 9+, the rest at 8.3–8.5, with stated limits."

## 8. Verification summary (exit criteria per phase)

- **P0.**
  - CI green on `main`. `stamp --check` and `check_release_artifacts` exit 0.
  - Axe: 0 violations.
  - Fence gate present and green.
  - `check_figure_axes` shows 2 warnings.
  - Short-copy and registry checks exit 0.
  - `/health` = HEAD.
  - 15 diagrams checked in a browser.
- **P1.**
  - No `src/` write to `_meta`.
  - 10 CIs are in `metrics.json`, equal to history, and gated.
  - 12 variant JSON gated, with `metrics.json` unchanged.
  - 03 NAB JSON gated, with the null and perfect baselines sane.
  - Restamped.
- **P2.**
  - Each new artifact is under `reports/…_<date>/`, reconciles to its summary, and is gated.
  - Spend is within the cap and recorded by the project meter.
- **P3.**
  - The reproduction checks (02 members, 12 → 13) pass before any curve or headline is replaced.
  - New hardware is recorded in `evaluation_metadata.json`.
