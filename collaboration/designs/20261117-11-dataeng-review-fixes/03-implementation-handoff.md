# Implementation handoff: 11 spread per cell, negative parity test, ladder total

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/11-data-engineering.md`

## Objective

Show spread beside the medians, add a negative parity test, and reconcile the "19x / 15x" ladder total with the table and say what it is.

## Scope

### In scope
- `projects/11-data-engineering/src/data_engineering/` (spread from existing repeats; parity test target only)
- `projects/11-data-engineering/tests/` (negative parity test)
- `projects/11-data-engineering/README.md` and `story.yaml` (results table, ladder total sentence)
- `reports/metrics.json`, `reports/results.md` (spread fields)
- Figures `task_times_dotplot`, `speedup_overview` (spread and sqlite legend entry)
- `apps/showcase-web/src/lib/storyShort.ts` (regenerated if copy changes)

### Out of scope
- Re-running the 8-minute benchmark (owner approval; use the recorded repeats)
- Changing the tasks or the parity contract
- Mapping to ClickBench (owner decision; see below)

## Ordered steps

1. **Spread.** From the five recorded warm repeats per cell, add min and max (or IQR) to `metrics.json`. Show them as whiskers or a second table column. Use only recorded repeats; do not re-time.
2. **Ladder total.** Compute the ladder total the same way the copy does (state the formula in one sentence), and check it against the table. If "19x / 15x" does not match the formula, correct the copy to the value the formula gives and say so in the completion report.
3. **sqlite legend.** Add sqlite as a legend entry on `task_times_dotplot` marked n/a for `write_parquet`.
4. **Negative parity test.** Add a test that feeds a deliberately wrong engine result (one row changed) and asserts the parity check fails.
5. Regenerate the affected figures and metrics with the project CLI from recorded data.

## Owner decision required

- **ClickBench mapping.** Mapping these tasks to ClickBench is a methodology claim that needs checking against the current ClickBench definition. Owner decides whether to do it; Kimi does not claim the mapping in this handoff.

## Commands and gates

```bash
uv run pytest -q projects/11-data-engineering/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Spread (min and max or IQR) present per cell from recorded repeats.
- [ ] Ladder total formula stated and copy matches it.
- [ ] sqlite appears in the legend with n/a for write_parquet.
- [ ] Negative parity test fails on a deliberately wrong result.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause if the recorded repeats are missing for any cell; report the count.
