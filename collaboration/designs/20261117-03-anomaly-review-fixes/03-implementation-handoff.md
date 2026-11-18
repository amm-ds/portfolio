# Implementation handoff: 03 anomaly metric framing and copy split

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided; the NAB official score is an owner decision, see below)
Source review: `collaboration/reviews/20261117-experiment-review/03-anomaly-detection.md`

## Objective

Split the headline sentence so raw and budgeted alert counts are never in one sentence, add confidence intervals to the precision values quoted, and label the random band on `range_pr`.

## Scope

### In scope
- `projects/03-anomaly-detection/story.yaml` (`short_version`)
- `projects/03-anomaly-detection/README.md` (precision values, metric definitions)
- `projects/03-anomaly-detection/src/anomaly_detection/` (interval computation for precision only, if not already committed)
- `reports/nab_metrics.json` (intervals, if added)
- Figure `range_pr` (random band label)
- `apps/showcase-web/src/lib/storyShort.ts` (regenerated)

### Out of scope
- Changing the detectors, the budget, or the frozen operating point
- Computing the NAB official score (owner decision, see below)

## Ordered steps

1. **Split headline.** Rewrite `short_version` as two sentences: (a) raw detector alert count and incidents touched; (b) the budgeted comparison, stating the page count and the like-for-like range-F1. Keep each number traceable to `reports/nab_metrics.json`.
2. **Precision intervals.** Add a bootstrap interval for precision at the 2% budget (0.527) and for the no-skill band, committed in `nab_metrics.json`. Use a fixed seed and state the resample count.
3. **Metric definitions.** Add one table in the README defining range-F1, range-PR, range recall, and precision as used here, and which configuration each table row refers to.
4. **Label.** Label the random band on `range_pr` directly on the figure.
5. Regenerate `storyShort.ts` and the figure with the project CLI.

## Owner decision required

- **NAB official score.** Either compute it (it needs the official scorer and application profiles; a new dependency or vendored code) or state on the card that it is not reported and why. Owner decides which.

## Commands and gates

```bash
uv run pytest -q projects/03-anomaly-detection/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
uv run python scripts/lint_story_language.py
```

## Acceptance criteria

- [ ] `short_version` has two sentences, raw and budgeted kept apart.
- [ ] Precision intervals committed and cited.
- [ ] Metric definitions table present; each row names its configuration.
- [ ] Random band labelled on `range_pr`.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause before adding a NAB scorer dependency; owner decides first.
