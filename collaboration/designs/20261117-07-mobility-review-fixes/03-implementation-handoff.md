# Implementation handoff: 07 mobility rounding, coverage outliers, and selection test

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/07-open-data-mobility.md`

## Objective

Reconcile the −28.2% versus −28.3% MAE reduction, name the coverage outliers in the headline, and add a test that validation selects the served model.

## Scope

### In scope
- `projects/07-open-data-mobility/src/mobility/` (the MAE reduction calculation and selection test target only)
- `projects/07-open-data-mobility/tests/` (selection test; rounding test)
- `projects/07-open-data-mobility/README.md` and `story.yaml` (headline sentence, rounding, coverage outliers, card wording)
- `reports/metrics.json` (unrounded reduction value, if not already present)
- `apps/showcase-web/src/lib/storyShort.ts` (regenerated)

### Out of scope
- Changing the served model, the band method, or the holdout
- Re-running the full pipeline; use committed metrics for the reconciliation

## Ordered steps

1. **Rounding.** Compute the MAE reduction from the unrounded MAE values in `metrics.json` for `gbm_tuned` and `naive_lag24`. Record the value. Make the table and the headline show the same rounded value (−28.2% if the unrounded value gives that). State in the completion report which value you chose and why.
2. **Coverage outliers.** Add to the headline sentence that coverage holds overall (90.8%) and that the no-borough bucket (84.7%) and Staten Island (98.5%) are the outliers.
3. **Selection test.** Add a test that the served model is chosen by validation MAE, using a fixture where test MAE is swapped to favour a challenger; the served model must not change.
4. **Card wording.** State on the card that the GBM is compared against persistence only.
5. Regenerate `storyShort.ts` if the short copy changes.

## Commands and gates

```bash
uv run pytest -q projects/07-open-data-mobility/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Reduction value is identical in table, headline, and copy, with the unrounded source recorded.
- [ ] Coverage outliers are named in the headline.
- [ ] Selection test passes and fails under a swapped test MAE.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause if the unrounded MAE values are not committed; report instead of recomputing.
