# Implementation handoff: 07 xGB definition and 09 design correction note

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-19: keep "xGB" as the challenger's name; keep the DESIGN.md sentence with a correction note)
Source design: `collaboration/reviews/20261119-execution-review/00-review.md` (minor items), owner decision recorded in this handoff

## Objective

Make two small copy changes with no number or label changes:

1. In project 07, define "xGB" once as XGBoost at first use, so readers know it is the challenger and not the served model.
2. In project 09's DESIGN.md, keep the historical "8 unplanned calls" sentence and add a correction note pointing to the Q1 removal.

## Decision recorded

- "xGB" stays as the short name of the XGBoost challenger. It is NOT renamed to "served GBM". The served model is the "tuned GBM" (figure caption, `docs/projects/07-open-data-mobility.md:13`). Renaming the challenger would mislabel the test leader.
- Predeclared labels and committed keys stay unchanged: `xGB versus naive` (`story.yaml:205`, `:372`, `:426`; `docs/projects/07-open-data-mobility.md:60`), `xgb_tuned` and `xgb_tuned_vs_naive_lag` in `reports/metrics.json`, and `DESIGN.md:115`.

## Scope

### In scope

- `projects/07-open-data-mobility/story.yaml`: first use of "xGB" in the body (line 27, "xGB is best on test at −31.2%") gets the definition "xGB (XGBoost)". Do not repeat the definition at later uses. Line 190 already reads "xGB is XGBoost, and LightGBM is another"; leave it.
- `docs/projects/07-open-data-mobility.md`: first use of "xGB" (line 38, "the xGB challenger") gets "xGB (XGBoost)" if the page does not already define it earlier. Check the page top before editing.
- `projects/09-agentic-workflows/DESIGN.md`: after line 181 ("(8 unplanned calls)"), add one correction sentence (below).
- `storyShort.ts` and `short_version` only if the 07 edit changes their text. Regenerate through `scripts/gen_story_short.py`; never hand-edit.

### Out of scope

- Any rename of "xGB" to "served GBM" anywhere.
- Predeclared labels, table rows, metric keys, and committed JSON or report files.
- Any change to 07 numbers, figures, or the served-model wording.
- Any other 09 DESIGN.md text.
- Hosted calls, deploys, git mutations, `.env`, permissions, or config changes. Do not commit.

## Affected surfaces

- `projects/07-open-data-mobility/story.yaml`
- `docs/projects/07-open-data-mobility.md`
- `projects/09-agentic-workflows/DESIGN.md`
- `apps/showcase-web/src/lib/storyShort.ts` (only if regenerated)

## Ordered implementation steps

1. Read `projects/07-open-data-mobility/story.yaml` lines 20–30 and 185–200, and `docs/projects/07-open-data-mobility.md` lines 1–40. Confirm which "xGB" is the first use on each surface.
2. In `story.yaml` line 27, change the first "xGB" to "xGB (XGBoost)". Make no other edit to that line.
3. In `docs/projects/07-open-data-mobility.md`, apply the same first-use definition if it is not already defined earlier on the page.
4. In `projects/09-agentic-workflows/DESIGN.md`, directly after the line containing "(8 unplanned calls)" (around line 181), insert this sentence on a new line inside the same bullet:
   `Correction (2026-11-19): the "8 unplanned calls" count has no committed artifact behind it and is removed from the public copy; this record is kept for design history.`
5. If `story.yaml` short copy changed, run `uv run python scripts/gen_story_short.py` to regenerate `storyShort.ts`. If it did not change, run `--check` only.
6. Write the change list and gate output to `collaboration/reviews/20261119-xgb-naming-and-design-note/00-report.md`.

## Commands and gates

Run in this order:

```bash
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/check_headline_numbers.py
cd apps/showcase-web && npm test && npm run lint && npm run build
```

Also run `uv run pytest -q projects/07-open-data-mobility` only if a file under `projects/07-open-data-mobility/src` or `tests` changed. It should not, so expect no run.

Report the actual output of each gate. Do not claim a gate passed unless you ran it.

## Stop conditions

- If "xGB" in the first-use sentence cannot be defined without renaming a predeclared label, stop and write `OPEN_QUESTIONS.md` beside this handoff.
- If any headline number would change, stop and report.
