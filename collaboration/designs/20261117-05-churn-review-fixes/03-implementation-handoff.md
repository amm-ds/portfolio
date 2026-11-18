# Implementation handoff: 05 churn cost weights and holdout-read test

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/05-ml-pipeline-churn.md`

## Objective

State the cost weights next to every cost figure, mark the chosen threshold on the cost curve, and add a test that the holdout is not read when the threshold is chosen.

## Scope

### In scope
- `projects/05-ml-pipeline-churn/src/churn_pipeline/` (threshold selection test target only; no logic change)
- `projects/05-ml-pipeline-churn/tests/` (holdout-isolation test)
- `projects/05-ml-pipeline-churn/README.md` and `story.yaml` (cost weights beside 1,035 and 601)
- `reports/figures/business_cost_curve.html|json` (threshold marker)
- Regenerated: `apps/showcase-web/src/lib/storyShort.ts` if copy changes

### Out of scope
- Changing the cost weights, threshold, calibration, or model
- Re-running the full pipeline unless the figure regeneration requires it

## Ordered steps

1. **Cost weights.** Find the cost weights used in the pipeline config. Add them beside every cost figure in the README and card, for example "cost per missed churner and per contact". If the weights are not in config, stop and report.
2. **Threshold marker.** Add a vertical line at the frozen threshold (0.175) on `business_cost_curve`, labelled "frozen threshold".
3. **Holdout-isolation test.** Write a test that threshold selection uses only training OOF predictions. Use a fixture where holdout labels are replaced with sentinels; the chosen threshold must not change.
4. Regenerate only the affected figure with the project CLI.

## Commands and gates

```bash
uv run pytest -q projects/05-ml-pipeline-churn/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Cost weights appear beside each cost figure, traced to config.
- [ ] Threshold marker is on the curve and labelled.
- [ ] Holdout-isolation test passes and fails under a sentinel holdout read.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause if the cost weights are not in config.
