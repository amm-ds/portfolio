# Implementation handoff: 12 champion wording and validation interval

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/12-tabular-ml-lifecycle.md`

## Objective

Give the MLP-versus-LightGBM validation difference a paired interval, state the tie explicitly if the interval includes zero, and add a validation-only selection test.

## Scope

### In scope
- `projects/12-tabular-ml-lifecycle/src/tabular_ml_lifecycle/` (paired validation interval; selection logic only if the test requires it)
- `projects/12-tabular-ml-lifecycle/tests/` (selection test)
- `projects/12-tabular-ml-lifecycle/README.md` and `story.yaml` (champion wording, key findings)
- `reports/metrics.json` (new interval field)
- `reports/figures/model_comparison` and `residual_heatmap` only if the label or legend fix requires it

### Out of scope
- Retuning the MLP or LightGBM, or changing the 50-trial Optuna search
- Changing the frozen test window
- Changing the champion by test MAE (forbidden by the protocol)

## Ordered steps

1. **Paired validation interval.** Compute a paired bootstrap interval on validation MAE difference (MLP minus LightGBM), 2,000 resamples, fixed seed, using the committed validation predictions. Commit it in `metrics.json`.
2. **Wording.** If the interval includes zero, change "champion" to "tied on validation; the MLP is selected by the stated tie-break" and state the tie-break. The tie-break must be decided before reading test results: propose it in the completion report and wait for owner confirmation before committing the wording.
3. **Test.** Add a test that champion selection reads validation predictions only. Use a fixture where test predictions are sentinel values; selection must not change.
4. **Legends.** Confirm `residual_heatmap` has a legend and units. Fix only if missing.
5. Regenerate with the project CLI. Do not hand edit figures or metrics.

## Commands and gates

```bash
uv run pytest -q projects/12-tabular-ml-lifecycle/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Validation interval committed with seed and resample count.
- [ ] Wording matches the interval; tie-break is stated if used.
- [ ] Selection test passes and fails under a sentinel test read.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause before changing any champion wording; owner confirms the tie-break first.
