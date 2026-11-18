# Implementation handoff: 04 NLP cascade claim and table comparability

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/04-nlp-classification.md`

## Objective

Replace the cascade-gain claim with a paired interval, make the int8 row comparable to the other rows, add a cascade routing test, and round the headline numbers.

## Scope

### In scope
- `projects/04-nlp-classification/src/nlp_classification/` (cascade evaluation and the statistics helper, if one is used)
- `projects/04-nlp-classification/tests/` (new tests)
- `projects/04-nlp-classification/README.md` (Results and serving-economics tables)
- `projects/04-nlp-classification/story.yaml` (`short_version` and any cascade sentence)
- `reports/llm_cascade.json` and `reports/latency_probe.json` only if the paired interval is written there
- Regenerated: `apps/showcase-web/src/lib/storyShort.ts`

### Out of scope
- Re-running the LLM cascade on any split (paid provider calls need separate owner approval)
- Changing the chosen threshold τ=0.6 or the batch size
- New models or new splits

## Ordered steps

1. **Blocker.** Compute a paired bootstrap interval on the difference in macro-F1 (cascade minus transformer) on the fresh 1,000 split, using the existing committed predictions. Use the same resample count and seed convention as project 05 (2,000 resamples, fixed seed). Record it in `reports/llm_cascade.json`. No new provider calls.
2. **Reword the claim.** If the interval includes zero, change copy from "lifts" to "no measurable change" in `short_version`, README, and any figure caption. If the interval excludes zero, state the interval with the point estimate.
3. **int8 comparability.** The int8 row's quality is measured on a 2,000-row train sample, while other rows use the 1,000-row test. Either (a) measure fp32 and int8 on the same split and same metric, or (b) move the int8 row to a separate table labelled "train-sample quality". Choose (b) unless (a) needs no new model runs; state the choice in the completion report.
4. **Cascade routing test.** Add a test that the cascade sends exactly the rows with confidence below τ to the LLM, using a stub LLM client that counts calls.
5. **Rounding.** In `short_version` and headline copy, round to three decimals (0.953 → 0.954 style) and keep full values in the tables.
6. **Licence.** Replace "License unknown" with the dataset's stated licence, or remove the line. Report which.
7. Regenerate `storyShort.ts`.

## Commands and gates

```bash
uv run pytest -q projects/04-nlp-classification/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Paired interval on the fresh-split macro-F1 difference is committed and cited.
- [ ] Cascade-gain copy matches the interval (no "lift" when it includes zero).
- [ ] int8 is comparable or clearly separated.
- [ ] Cascade routing test passes and fails when τ logic is broken.
- [ ] Headline numbers are rounded in copy; full values in tables.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause and write `OPEN_QUESTIONS.md` if the interval needs predictions that are not committed, since that would require paid calls.
