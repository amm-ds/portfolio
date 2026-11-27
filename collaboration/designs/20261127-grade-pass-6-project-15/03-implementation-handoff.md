# Implementation handoff: grade pass 6, project 15 (option B)

Date: 2026-11-27
Designer: Claude Code
Executor: Kimi Code
Status: approved (2026-11-27). Decisions applied: project 15 held at 9.0; rubric mapping as proposed; figure C deferred.
Source design: `collaboration/designs/20261127-grade-pass-6-project-15/01-design-brief.md`

## Objective

Close the project 15 gaps that the Opus review named, without changing any committed RL metric value, the sealed-access log, or any verdict. Add a committed, script-computed breakdown of the paired RL − B1 gap by elasticity tercile and stock pressure, fill the model card, add a code excerpt, and remove the overclaims.

## Scope

### In scope

- `projects/15-dynamic-pricing-rl/` only, plus `docs/projects/15-dynamic-pricing-rl.md` and the phase-7 grade record.
- A new analysis script under `projects/15-dynamic-pricing-rl/scripts/` (or the project's existing analysis location, whichever the project uses; state which).
- `reports/metrics.json` gains an `analysis` key. Nothing else in `metrics.json` changes.
- `MODEL_CARD.md`, `story.yaml`, `docs/projects/15-dynamic-pricing-rl.md`, `README.md` (only the lines that name limits or seeds).
- The phase-7 record: 15 row and the "15 stays" note, per the owner's decision on the grade hold.

### Out of scope

- Any new policy evaluation, any new sealed read, any change to `sealed_access.json`.
- Any change to a committed RL value in `metrics.json` outside `analysis` and `_meta`.
- Projects 01, 08, and the other twelve stories.
- Any hosted or paid call.
- Figure C (per-episode histogram) unless the owner approves it after step 6.
- Any git mutation. The owner commits.

## Affected surfaces

- `projects/15-dynamic-pricing-rl/reports/metrics.json` (new `analysis` key only)
- `projects/15-dynamic-pricing-rl/scripts/<analysis script>.py` (new)
- `projects/15-dynamic-pricing-rl/tests/` (one test for the analysis script)
- `projects/15-dynamic-pricing-rl/story.yaml`
- `projects/15-dynamic-pricing-rl/MODEL_CARD.md`
- `projects/15-dynamic-pricing-rl/README.md`
- `docs/projects/15-dynamic-pricing-rl.md`
- `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-7-result.md`

## Ordered implementation steps

1. **Baseline snapshot (before any edit).** Record `sha256sum` of `reports/metrics.json`, `reports/sealed_access.json`, `reports/test_episodes.json`. Save a copy of `metrics.json` to the scratchpad for the diff check in step 8.
2. **Write the analysis script.** It reads `reports/test_episodes.json` only. It computes, from per-episode records:
   - paired difference RL − B1 per episode;
   - mean and 95% bootstrap CI (2,000 resamples, seed 42, episode unit) by elasticity tercile of the episode's elasticity draw, from least to most price-sensitive;
   - RL episode win share (fraction of episodes with RL > B1);
   - the same paired mean by stock pressure `rho` in {0.7, 1.0, 1.3}.
   If `test_episodes.json` does not carry the elasticity or `rho` per episode, stop and report. Do not infer them from other files and do not run the simulator.
3. **Add a test.** Assert the script reproduces the tercile and win-share numbers on a fixed fixture, and that it refuses to run if `sealed_access.json` is missing or has more than three reads. Do not read the sealed files for values in the test.
4. **Run the script** and write its output into `reports/metrics.json` under `analysis`. Record the script path and its git sha inside the key. Restamp with `scripts/stamp_metrics_meta.py`. Confirm `_meta` is the only other key that changed.
5. **Copy edits in `story.yaml`:**
   - Lead: gloss M5, MaskablePPO, action mask, comparator in one short sentence each.
   - Training: add a code excerpt taken from source (the action-mask function or the paired bootstrap). Quote it exactly from the file and name the file and line.
   - Training and limits: state that only seed 1 was retained, and that B1 also beat RL on validation (0.5225 vs 0.5144, from `baselines_val.json` and `ppo_val.json`).
   - Results: add the tercile breakdown and the win share, using only numbers from the `analysis` key. Replace "That gap is consistent across repeated checks" with "Resampling the 1,000 test games keeps the learner behind in every resample, so the gap is not luck in this test." Check the claim against the bootstrap output before keeping it; if the bootstrap does not show that, use weaker wording.
   - Replace "a fair testing setup that proves safe behaviour" with "shows zero rule breaks in every simulated test."
   - Replace "It learned well" with "It beat three simpler rules."
   - Conclusions: add `## Results summary` above the existing text.
   - Replace "fixed `1.30×` multiplier" with "holds 1.30× after a 14-day masked ramp", after checking the ramp length in `reports/price_traces.json` or the price-trace data. If the ramp cannot be verified, do not state it and report.
6. **Mirror to the docs page.** `docs/projects/15-dynamic-pricing-rl.md` must match every changed claim.
7. **Fill `MODEL_CARD.md`:** intended use (simulator research only, not for deployment), data (M5-calibrated, item-level split, seed 42), metrics by slice (from `analysis`), limits (one retained seed, simulator only, elasticity is an assumption, no reference-price or substitution effects).
8. **Diff check.** Compare the new `metrics.json` with the step 1 copy. Every changed value must be under `analysis` or `_meta`. Re-hash `sealed_access.json` and `test_episodes.json`; both must match step 1.
9. **Regenerate** `gen_static_registry.py` and `gen_story_short.py`. Do not edit their output by hand.
10. **Grade record.** Hold project 15 at 9.0 (owner decision). Edit the 15 row (per-axis 9/9/9/9 per the record's own axes, or the Opus-based 9/9/9/8.5 mapping, stated explicitly), the 15 note, and the "12 of 14 at 9.0 or above (15 at 9.3)" headline in `phase-7-result.md`. Set the headline to match the held grade. Do not claim 9.3.

## Commands and gates

Run the narrow checks first, then the broader gates.

```bash
# narrow
uv run pytest projects/15-dynamic-pricing-rl -q -o addopts=""
uv run ruff check projects/15-dynamic-pricing-rl
uv run ruff format --check projects/15-dynamic-pricing-rl
uv run mypy libs projects apps
uv run python scripts/lint_story_language.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_docs.py
uv run python scripts/check_demo_contract.py
uv run python scripts/check_diagram_fences.py
uv run python scripts/check_figure_axes.py
uv run python scripts/check_figure_budget.py
uv run python scripts/stamp_metrics_meta.py --check

# broader (run once, after all edits)
uv run ruff check .
uv run ruff format --check .
uv run mkdocs build --strict
git diff --check
cd apps/showcase-web && npm test && npm run lint && npm run build
```

Record every exit code in `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-6-result.md` as a short addendum headed "grade pass 6".

## Generated artifacts

- `reports/metrics.json` (`analysis` key, restamped via `stamp_metrics_meta.py`)
- Static registry and story short, via `gen_static_registry.py` and `gen_story_short.py`

## Acceptance criteria

- [ ] `analysis` key present, computed by the committed script, with the script path and sha inside it.
- [ ] No committed RL value outside `analysis` and `_meta` has changed (step 8 diff is empty).
- [ ] `sealed_access.json` and `test_episodes.json` hashes match step 1.
- [ ] `MODEL_CARD.md` filled; no template text left.
- [ ] Code excerpt present in `story.yaml` training, quoted from source with file and line.
- [ ] Every new number in copy traces to a key in `analysis` or an existing committed value.
- [ ] Each overclaim named in the brief is replaced; the replacement wording is in the completion report.
- [ ] `story.yaml` and `docs/projects/15-dynamic-pricing-rl.md` agree on every changed claim.
- [ ] All narrow and broader gates exit 0, or the failure is recorded and the step stops.
- [ ] No co-author trailer in any commit message; no git mutation.

## Verification evidence required

- Pytest result for the project 15 suite: count and exit code.
- Each gate in the list above: exit code.
- Before and after hashes of `metrics.json` (outside `analysis`), `sealed_access.json`, `test_episodes.json`.
- The new `analysis` key, pasted in full in the completion report.
- The exact replacement sentences for each overclaim.
- Artifact paths inspected.

## Risks and open questions

- If `test_episodes.json` lacks per-episode elasticity or `rho`, step 2 stops. The fallback is to report the gap by rho only, if rho is present, and say so. Do not infer elasticity from the sample.
- The bootstrap may not support "not luck" wording. Use the weaker wording the numbers support.
- Owner decisions applied: 15 held at 9.0; rubric mapping as proposed. Do not reopen them in this round.
- Project 01 and 08 remain capped; this handoff does not change them.
- Stop and write `OPEN_QUESTIONS.md` beside this handoff if any step needs a sealed file read, a paid call, or a change to a committed RL value.
