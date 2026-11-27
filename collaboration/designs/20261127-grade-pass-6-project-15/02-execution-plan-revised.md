# Grade pass 6, project 15: revised execution plan (option B)

Date: 2026-11-27
Revises: the execution plan pasted for Kimi (same date). Governed by `03-implementation-handoff.md` (approved) and `01-design-brief.md`.
Base: branch HEAD `8d1920ed`. Working tree only; no commits.

## Hard constraints

- No git mutations by Kimi. All changes stay uncommitted. The owner reviews and commits. No co-author trailers.
- No new sealed read, no policy evaluation, `sealed_access.json` byte-untouched. No hosted or paid calls.
- No change to any committed RL metric value outside `analysis` and `_meta`.
- Never touch `projects/08-inference-serving/data/bench_run_repeat.json`. Projects 01, 08 and the other twelve stories are out of scope.
- If any step needs a sealed-file read, a paid call, or a committed RL value change: stop and write `OPEN_QUESTIONS.md` beside the handoff.

## Verified facts this revision relies on

Checked against the repo on 2026-11-27:

- `reports/test_episodes.json` has three top-level keys: `selection`, `sets`, `price_traces`. It is not a flat per-episode list.
- Per-episode inputs for the test set are at `sets.test.specs[i]` (keys `epsilon`, `rho`, `seed`, `series_id`). Per-episode outcomes are at `sets.test.policies.<P>.normalised_profit[i]`. Both lists have length 1000 and are aligned by index `i`.
- `reports/price_traces.json` does NOT exist. Price traces live at `price_traces.<episode>.policies.<P>`, a list of 91 daily records with keys `day`, `multiplier`, `price`, `inventory`, `sales`.
- Ramp, from the three traces (episodes 89, 654, 773): B1 starts at 1.10×, reaches 1.20× on day 7, and reaches 1.30× on day 14, then holds 1.30× for 77 days. So "holds 1.30× after a 14-day ramp from 1.10×" is verified. "Masked" is not verified from the trace alone; do not use it.
- RL days at 1.20×: 43, 41, 40 across the three traces. This matches the Opus figure.
- `scripts/stamp_metrics_meta.py` requires `_meta.git_sha` to be an ancestor of HEAD whose payload (with `_meta` excluded) is identical to the current payload. An uncommitted payload change therefore fails `--check` until the owner commits. The gate is expected to fail before the commit. Record it as a failure with that cause. Do not hide it.

## Corrections to the pasted plan

1. **Step 2, the elasticity field.** Use `specs[i].epsilon` and `specs[i].rho`, not a per-episode field the pasted plan assumed. Define the tercile explicitly: sensitivity = |epsilon|, cut at the 1/3 and 2/3 quantiles of |epsilon| over the 1000 test episodes. "Least to most sensitive" means ascending |epsilon|. State the cut values in the key.
2. **Step 2, the "not luck" test.** Compute the fraction of the 2,000 bootstrap resamples in which the mean RL − B1 difference is below zero. Report it as "X of 2,000 resamples". The phrase "in every resample" may be used only if X = 2000.
3. **Step 4, the git sha.** Do not write a git sha into the `analysis` key. Nothing is committed, so the key would name the wrong commit. Record the script path and `sha256` of the script file instead. Then, in the completion report, list the restamp sequence for the owner (below).
4. **Step 4, the gate failure.** Expected: `stamp_metrics_meta --check` fails before the commit. Record its exit code and cause. Owner sequence after commit: commit the payload, run `stamp_metrics_meta.py` to restamp, verify `--check` exits 0, then commit the `_meta` change separately.
5. **Step 5, the ramp wording.** Use: "B1 climbs from 1.10× to 1.30× over the first 14 days, then holds 1.30× for the rest of the episode." Use the ramp sentence only after step 5 re-reads the three traces. Do not write "masked" unless a committed source says the mask causes it.
6. **Step 5, the README.** The pasted plan omitted it. The handoff scope includes `README.md`, limited to the lines that name seed retention or limits. Add it.
7. **Step 10, the grade axes.** The pasted plan said "axes mapping stated explicitly", which is ambiguous. Use this rule instead:
   - Results: 9 (Opus scored 9; the pass-5 record had 10, which is withdrawn).
   - Contents: 9.
   - Visualizations: 9 (the existing charts are useful; the record had 9).
   - Technologies (Best practices folded in): 9 only if the model card (step 7) and the code excerpt (step 5) both land. If either is missing, 8.
   - Result: 9/9/9/9 = 9.0 when Technologies is 9. 9/9/9/8 = 8.8 otherwise. Record whichever applies. Do not claim 9.0 unless both items landed.
   - Headline: "12 of 14 at 9.0 or above" if 15 is 9.0 with T=9. Otherwise, make the headline reflect 15 at 8.8.
8. **Step 2, the assumption.** Opus's per-tercile and win-share figures were computed in-session from these same files. They are not committed. Step 2 must recompute them from the committed data and must not copy the in-session numbers. If a recomputed number differs from the Opus figure, use the recomputed one and report the difference.

## Ordered steps

1. **Baseline.** Record sha256 of `reports/metrics.json`, `reports/sealed_access.json`, `reports/test_episodes.json`. Copy `metrics.json` to the scratchpad for the step 8 diff.
2. **Analysis script** at `projects/15-dynamic-pricing-rl/scripts/analyse_gap_by_slice.py` (or the project's existing analysis location; state which). Reads `reports/test_episodes.json` only. Computes, using `specs` and `policies` aligned by index:
   - per-episode difference RL − B1;
   - mean and 95% bootstrap CI (2,000 resamples, seed 42, episode unit) by |epsilon| tercile;
   - RL win share (fraction of episodes with RL > B1);
   - the same paired mean by `rho` in {0.7, 1.0, 1.3};
   - the fraction of resamples with mean difference < 0.
   Stop and write `OPEN_QUESTIONS.md` if any field is missing.
3. **Test** `projects/15-dynamic-pricing-rl/tests/test_analyse_gap_by_slice.py`. Use a synthetic fixture, not sealed values. Assert the script reproduces tercile and win-share results on the fixture. Assert it refuses to run if `sealed_access.json` is missing or has more than three reads. Do not read sealed values in the test.
4. **Run** the script. Write output to `reports/metrics.json` under `analysis`. The key includes the cut values, the script path, and the script's sha256. Restamp is expected to fail the gate until commit (see correction 4). Confirm `_meta` is the only other changed key.
5. **Copy edits in `story.yaml`:**
   - Lead: one short gloss each for M5, MaskablePPO, action mask, comparator.
   - Training: code excerpt quoted exactly from source, with file and line.
   - Training and limits: only seed 1 retained; B1 also beat RL on validation (0.5225 vs 0.5144, from `baselines_val.json` and `ppo_val.json`). Confirm both numbers from the files before writing them.
   - Results: tercile breakdown and win share, from the `analysis` key only; the "X of 2,000 resamples" wording.
   - Overclaim replacements per handoff §5. "Proves safe behaviour" → "shows zero rule breaks in every simulated test." "It learned well" → "It beat three simpler rules."
   - Conclusions: add `## Results summary`.
   - Ramp sentence per correction 5.
6. **Mirror** every changed claim to `docs/projects/15-dynamic-pricing-rl.md`.
7. **Model card** `MODEL_CARD.md`: intended use (simulator research, not for deployment), data (M5-calibrated, item-level split, seed 42), metrics by slice from `analysis`, limits (one retained seed, simulator only, elasticity assumption, no reference-price or substitution effects). No template text left.
8. **README** lines that name seed retention or limits (correction 6).
9. **Diff check.** `metrics.json` differs from the step 1 copy only under `analysis` and `_meta`. Re-hash `sealed_access.json` and `test_episodes.json`; both must match step 1.
10. **Regenerate** `gen_static_registry.py` and `gen_story_short.py`. Do not hand-edit outputs.
11. **Grade record** `phase-7-result.md`: apply correction 7. Edit the 15 row, the 15 note, and the headline line. No 9.3 anywhere.

## Gates

Record every exit code in `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-6-result.md` under a "grade pass 6" addendum.

Narrow:
- `uv run pytest projects/15-dynamic-pricing-rl -q -o addopts=""`
- `uv run ruff check projects/15-dynamic-pricing-rl`
- `uv run ruff format --check projects/15-dynamic-pricing-rl`
- `uv run mypy libs projects apps`
- `uv run python scripts/lint_story_language.py`
- `uv run python scripts/check_short_copy.py --check`
- `uv run python scripts/gen_static_registry.py --check`
- `uv run python scripts/gen_story_short.py --check`
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`
- `uv run python scripts/check_demo_contract.py`
- `uv run python scripts/check_diagram_fences.py`
- `uv run python scripts/check_figure_axes.py`
- `uv run python scripts/check_figure_budget.py`
- `uv run python scripts/stamp_metrics_meta.py --check` (expected to fail before commit; see correction 4)

Broader, once, after all edits:
- `uv run ruff check .` and `uv run ruff format --check .`
- `uv run mkdocs build --strict`
- `git diff --check`
- `cd apps/showcase-web && npm test && npm run lint && npm run build`

## Completion report (to the owner, for review and commit)

- The `analysis` key in full, with cut values and the script's sha256.
- Recomputed figures compared with the Opus in-session figures; any difference stated.
- Replacement sentences for each overclaim, verbatim.
- Before and after sha256 of `metrics.json` (outside `analysis`), `sealed_access.json`, `test_episodes.json`.
- Every gate exit code, including the expected `stamp --check` failure and its cause.
- The owner's post-commit restamp sequence (correction 4).
- Grade axes applied (correction 7) and the headline line.
- Artifact paths inspected.
- Anything not done and why.
