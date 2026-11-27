# Grade pass 6, project 15 — completion report (for owner review + commit)

Date: 2026-11-27. Branch HEAD at start: `8d1920ed`.
Status: all 11 steps of `02-execution-plan-revised.md` done; all gates exit 0
(except the expected pre-commit stamp failure, see §6). **Nothing committed;
all changes are in the working tree.**

## 1. The analysis key (in full)

`reports/metrics.json` → `analysis.gap_by_slice`:

- source: `reports/test_episodes.json`
- script: `src/dynamic_pricing/analyse_gap_by_slice.py`
- script_sha256: `1ad0b0a7bd241454760df0d2875738499f131a789c21a445ea81c813be367c46`
- method: per-episode paired RL − B1 normalised-profit difference;
  episode-unit percentile bootstrap, 2,000 resamples, seed 42
- by_elasticity_tercile (least → most sensitive, |epsilon|):
  - low (|ε| ≤ 2.178): mean −0.017418, CI [−0.020469, −0.014333], n = 334
  - mid (2.178 < |ε| ≤ 2.878): mean −0.010491, CI [−0.013817, −0.007294], n = 333
  - high (|ε| > 2.878): mean −0.001155, CI [−0.003301, +0.001033], n = 333
- elasticity_cuts_abs_epsilon: [2.178283468473902, 2.8780628203070946]
- rl_win_share: **0.351**
- by_rho: 0.7 → −0.008156 [−0.010691, −0.005517] (n = 334);
  1.0 → −0.010746 [−0.013669, −0.007953] (n = 333);
  1.3 → −0.010189 [−0.013893, −0.006994] (n = 333)
- resamples_below_zero: **2000 of 2000**
- n_resamples: 2000; seed: 42; n_episodes: 1000

## 2. Recomputed figures vs Opus's in-session figures

- Win share: Opus 35.1% → recomputed 0.351 (exact match).
- Tercile magnitudes: Opus −0.0013 / −0.0105 / −0.0174 → recomputed
  −0.001155 / −0.010491 / −0.017418 (same values at Opus's precision).
- **Ordering: no difference.** Opus listed the terciles "most to least
  sensitive" as −0.0013, −0.0105, −0.0174, so the least-sensitive third is
  −0.0174. The recomputed values (by ascending |epsilon|: low −0.0174,
  mid −0.0105, high −0.0012) match that direction. The largest loss is in the
  least price-sensitive third. The story states the same direction. An earlier
  draft of this section misread Opus's order as reversed; that claim is
  withdrawn.
- RL days at 1.20× (43/41/40 across episodes 89/654/773): matches the Opus
  figure.
- resamples_below_zero = 2000, so the "every resample" wording is allowed
  (revision correction 2).

## 3. Replacement sentences (verbatim, from story.yaml)

- Lead plain-terms: "It beat three simpler rules, but a simple fixed price
  still made more money in the final test." (was "It learned well, but…")
- Evaluation plain-terms: "All 2,000 resamples of the paired episode gaps
  stay negative, so the loss is not luck in this test, and every method
  followed every pricing rule." (was "That gap is consistent across repeated
  checks, while…")
- Final plain-terms: "The useful result is a fair testing setup that shows
  zero rule breaks in every simulated test and makes the loss clear instead
  of hiding it." (was "…a fair testing setup that proves safe behaviour…")
- Conclusions: "Under this simulator, `B1` climbs from `1.10×` to `1.30×`
  over the first `14` days, then holds `1.30×` for the rest of the episode,
  capturing margin that the learned policy does not recover." (was "a fixed
  `1.30×` multiplier captures margin…"; "masked" not used — the trace alone
  doesn't show it)
- Training addition: "B1 also beat the learner on validation: `0.5225`
  against seed `1`'s `0.5144` (`reports/baselines_val.json`,
  `reports/ppo_val.json`), so the test loss was visible before the sealed
  read."
- Limits addition: "**One retained seed:** only seed `1`'s checkpoint was
  kept, and `B1` also beat RL on validation (`0.5225` vs `0.5144`);
  seed-level variance is not measured."
- Conclusions gained a `## Results summary` heading before
  `## What the experiment taught`.
- Lead glosses in `key_concepts`: new entries for **M5** and
  **MaskablePPO** (action mask and comparator already covered by the
  existing "Action masking" and "Locked comparator" entries).

## 4. Code excerpt

`story.yaml` training now quotes `action_masks` verbatim from
`src/dynamic_pricing/env.py:183-197` (16 lines, with file and line named).

## 5. Model card

`MODEL_CARD.md` filled (was a 264-byte template): intended use (simulator
research, not for deployment), data (M5-calibrated, item-level split,
seed 42), the slice table from `analysis`, and the limits (one retained
seed, simulator only, elasticity assumption, no reference-price or
substitution effects). No template text left.

## 6. Integrity evidence

Baseline → after:

| file | sha256 before | after |
|---|---|---|
| `reports/metrics.json` | cfb5ddab4d436ff5… | changed only under `analysis` (no `_meta` write yet) |
| `reports/sealed_access.json` | ea508183322badca… | **unchanged** (re-hashed) |
| `reports/test_episodes.json` | 1f1d3a49dda0c32c… | **unchanged** (re-hashed) |

Diff check: `metrics.json` payload outside `analysis` and `_meta` is
byte-identical to the baseline copy (`scratchpad/p6-p15/metrics.before.json`).
`_meta` is unchanged so far (I did not stamp; see below).

## 7. Gates (exit codes)

Narrow, all 0: pytest 15 = 40 passed; ruff check / format on project 15;
mypy libs projects apps; lint_story_language; check_short_copy --check;
gen_static_registry --check; gen_story_short --check;
check_headline_numbers; check_docs; check_demo_contract;
check_diagram_fences; check_figure_axes; check_figure_budget.

Broader, all 0: ruff check .; ruff format --check .; mkdocs build --strict;
git diff --check; web npm test (771 passed), npm run lint, npm run build.

Expected failure, recorded not hidden: `stamp_metrics_meta.py --check`
FAILED with 3 stale `_meta` blocks (15's new analysis key; 13 and 12 from
the Phase 4 promotion). Cause: the stamp's `git_sha` must be an ancestor of
HEAD whose payload matches the current payload, which cannot hold before
the payload is committed.

**Owner's post-commit restamp sequence:** commit the payload → run
`uv run python scripts/stamp_metrics_meta.py` → verify `--check` exits 0 →
commit the `_meta` changes separately (15, 13, 12 are the stale ones).

## 8. Grade record applied

`phase-7-result.md` 15 row now reads **9.0 (held), 9/9/9/9**: Results 9
(Opus; the 10 withdrawn), Contents 9, Visualizations 9, Technologies 9 —
both prerequisites landed (model card + code excerpt), per the revised
plan's rule. The 9.3 record is withdrawn until the analysis is committed
and Opus confirms Results ≥ 9.5. The headline line now reads "12 of 14 at
9.0 (15 held at 9.0 pending Opus re-confirmation); 01 and 08 at 8.8…". The
downgrade note records the hold and its basis. The two remaining "9.3"
mentions are the required withdrawal notes, not grade claims.

## 9. Artifact paths inspected

- `reports/test_episodes.json` (structure: `sets.test.specs[i]` with
  `epsilon`/`rho`/`seed`/`series_id`; `sets.test.policies.<P>.normalised_profit[i]`;
  `price_traces.<episode>.policies.<P>` with 91 daily records)
- `reports/baselines_val.json` (B1 0.5224796738595361) and
  `reports/ppo_val.json` (seed 1 = 0.5143695547914966) — validation pair
  confirmed before writing
- `reports/sealed_access.json` (list of 3 `seal_read` entries; unchanged)
- `src/dynamic_pricing/env.py:183-197` (excerpt source)
- Ramp re-read in episodes 89/654/773: B1 1.10× → 1.20× day 7 → 1.30×
  day 14, holds through day 90

## 10. Files changed (uncommitted, for the owner's commit)

- `projects/15-dynamic-pricing-rl/src/dynamic_pricing/analyse_gap_by_slice.py` (new)
- `projects/15-dynamic-pricing-rl/tests/test_analyse_gap_by_slice.py` (new, 4 tests)
- `projects/15-dynamic-pricing-rl/reports/metrics.json` (`analysis` key only)
- `projects/15-dynamic-pricing-rl/story.yaml` (10 edits)
- `projects/15-dynamic-pricing-rl/MODEL_CARD.md` (filled)
- `projects/15-dynamic-pricing-rl/README.md` (seed-retention line)
- `docs/projects/15-dynamic-pricing-rl.md` (mirrored)
- `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-7-result.md` (grade hold)
- `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-6-result.md` (gate addendum)
- this report

## 11. Not done / notes

- No new sealed read, no policy evaluation, no hosted call, no metric value
  change, no git mutation — as required.
- Figure C (per-episode histogram) deferred per the owner's decision.
- The Opus tercile-ordering discrepancy is disclosed in §2 and explained in
  the story's results text.
