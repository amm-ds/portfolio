# Implementation handoff: 09 pass-rate intervals and legacy versus live labelling

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided; the live confirmation run is a separate approval, see below)
Source review: `collaboration/reviews/20261117-experiment-review/09-agentic-workflows.md`

## Objective

Give the pass rates intervals and repeat counts, and label every legacy number as legacy on every figure and table. Do not run the live confirmation in this handoff.

## Scope

### In scope
- `projects/09-agentic-workflows/src/agentic_workflows/` (evaluation summary: interval computation only)
- `projects/09-agentic-workflows/tests/` (interval test)
- `projects/09-agentic-workflows/README.md` and `story.yaml` (results labels and pass-rate wording)
- `reports/metrics.json` and `reports/report.html` (regenerated offline from `data/run_records.json`)
- Figures `node_waterfall`, `cost_latency_bars`, `suite_summary`, `tool_usage_matrix` (labels only)
- Regenerated: `apps/showcase-web/src/lib/storyShort.ts` if the short copy changes

### Out of scope
- Any live model call (paid endpoint; owner approval required per protocol)
- Changing grading logic or the workflow
- Changing the recorded run records

## Ordered steps

1. **Intervals.** Add a Wilson or exact binomial interval for each pass count (15/15, 13/13, 5/6, 18/19, 12/19), computed offline in `evaluate`. State the method in the code docstring.
2. **Labels.** Add "legacy recorded run" to every results table and figure title that uses `run_records.json`. Keep the word "legacy" in the headline sentence.
3. **Repeat count.** State that each task was run once, in the README and on the card.
4. **Test.** Add a test that the interval for 15/15 matches a hand-computed value and that the labels are present in the generated report.
5. Regenerate `metrics.json` and `report.html` offline with the project `evaluate` command. Do not call the model.

## Owner decision required

- **Live confirmation.** Re-running the fresh contract checks (answer preservation, 6/6 refusals, deadlines) against the hosted endpoint is paid and external. It needs a separate owner approval, with the budget stated, before any run. Not part of this handoff.

## Commands and gates

```bash
uv run pytest -q projects/09-agentic-workflows/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Every pass rate has an interval in `metrics.json` and in the README.
- [ ] Every legacy figure and table is labelled "legacy recorded run".
- [ ] Interval test passes against a hand-computed value.
- [ ] No model call is made; the report regenerates offline.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Do not call the hosted endpoint. Pause if regeneration would need a model call.
