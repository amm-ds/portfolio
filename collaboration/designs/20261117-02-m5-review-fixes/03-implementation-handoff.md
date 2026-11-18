# Implementation handoff: 02 M5 selection test and reconciled baseline

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/02-demand-forecasting.md`

The prod blocker (metrics guard) is a separate handoff: `collaboration/designs/20261117-metrics-guard-fix/`. Do not duplicate it here.

## Objective

Add the test that proves selection never reads the test origin, put the reconciled global LightGBM next to the ensemble in the headline table, and state the single-origin limit on the card.

## Scope

### In scope
- `projects/02-demand-forecasting/tests/` (new selection-isolation test)
- `projects/02-demand-forecasting/src/demand_forecasting/` (only the selection path, if the test exposes a leak)
- `projects/02-demand-forecasting/README.md` and `story.yaml` (headline table and the single-origin caveat)
- `reports_m5_full/metrics.json` and the headline table only if the reconciled number is not already committed; reuse committed reconciliation artifacts where possible
- Regenerated: `apps/showcase-web/src/lib/storyShort.ts` if `short_version` changes

### Out of scope
- Re-running the full M5 panel pipeline (multi-hour; needs owner approval)
- Changing the ensemble, candidates, weights, or protocol `m5_full_v1`
- The metrics-guard fix and the figure fixes (separate handoffs)

## Ordered steps

1. **Selection-isolation test.** Write a test that the selection and weight-fitting path reads only the two selection origins. Use a fixture where the test-origin actuals are replaced with sentinel values; the selected ensemble weights must be unchanged. If the test fails, stop and report the leak; do not fix it silently.
2. **Reconciled baseline.** Check `reports/reconciliation.json` for the reconciled global LightGBM WRMSSE on the same origin. If committed, add it to the headline table beside the ensemble, labelled with its origin. If not committed, stop and write `OPEN_QUESTIONS.md`; do not compute it without owner approval.
3. **Single-origin caveat.** Place "one scored test origin; no bootstrap interval" directly beside the headline 0.6161 in README and in `short_version` if space allows.
4. Keep the official WRMSSE wording consistent in all copy.

## Commands and gates

```bash
uv run pytest -q projects/02-demand-forecasting/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Selection-isolation test exists, passes, and fails under a deliberately injected test-origin read.
- [ ] Reconciled LightGBM appears beside the ensemble only if its number is committed; otherwise an open question is written.
- [ ] Single-origin caveat sits beside the headline number.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause and write `OPEN_QUESTIONS.md` if the isolation test shows a leak, or if the reconciled number is not committed.
