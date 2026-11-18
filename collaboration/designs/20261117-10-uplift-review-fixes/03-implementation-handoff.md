# Implementation handoff: 10 uplift copy and naming fixes

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/10-uplift-experimentation.md`

## Objective

Make the uplift copy state the analysed subset, stop calling revenue minus send cost "profit", and add the missing policy-selection and CUPED tests.

## Scope

### In scope
- `projects/10-uplift-experimentation/story.yaml` (`short_version` only)
- `projects/10-uplift-experimentation/README.md` (Results headline sentences and the profit labels)
- Profit labels in `projects/10-uplift-experimentation/src/uplift_experimentation/` (rename to revenue-minus-send-cost where it is a display label; do not change computed values)
- Generated outputs that carry those labels: `reports/figures/profit_frontier*.html|json`, and `apps/showcase-web/src/lib/storyShort.ts` (regenerate, never hand edit)
- Tests under `projects/10-uplift-experimentation/tests/` for CUPED and for policy selection

### Out of scope
- Any computed number, model, or policy choice
- Changing the recommended policy (T-learner stays)
- Dataset changes

## Ordered steps

1. **Blocker, copy.** In `short_version`, state that the analysis uses 42,613 customers (Men's E-Mail vs No E-Mail) from the 64,000-row Hillstrom dataset. Keep it within the 280-character limit.
2. **Naming.** Find every user-visible use of "profit" for `revenue − send cost` (grep `profit` in README, figure titles, story copy). Replace with "revenue minus send cost". Keep JSON keys unchanged unless renaming is a single, grep-verified change; if keys change, list them.
3. **Headline rounding.** Change "+69%" to "+70%" (2,812 / 4,026 = 69.9%) in the README and copy, or show one decimal. Pick one and say which.
4. **Policy rule.** Add one sentence to the README results stating the rule: the recommended policy is selected by profit at the 25% budget, and the response model has higher Qini with overlapping intervals.
5. **Tests.** Add (a) a CUPED test on synthetic data with a known variance reduction, and (b) a test that policy selection uses the stated profit rule and not the Qini value.
6. **Regenerate** `storyShort.ts` with `uv run python scripts/gen_story_short.py` and run `scripts/check_short_copy.py --check`.

## Commands and gates

```bash
uv run pytest -q projects/10-uplift-experimentation/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
uv run python scripts/lint_story_language.py
```

## Acceptance criteria

- [ ] `short_version` states 42,613 analysed of 64,000 rows, within 280 characters.
- [ ] No user-visible "profit" remains for revenue minus send cost; grep proves it.
- [ ] "+69%" or "+70%" is consistent everywhere, and the choice is stated in the completion report.
- [ ] The policy-selection rule sentence is present.
- [ ] Both new tests pass and fail on a deliberately broken input.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause and write `OPEN_QUESTIONS.md` if renaming a JSON key would break the showcase JSON contract.
