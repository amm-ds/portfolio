# Report: 07 xGB definition + 09 design correction note

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-xgb-naming-and-design-note/03-implementation-handoff.md`
Owner decision applied: "xGB" stays as the XGBoost challenger's name (NOT
renamed to "served GBM"); the DESIGN.md sentence stays with a correction
note. No commits, no hosted calls, no Q3b/Q3c/Q4.

## Changes

1. `projects/07-open-data-mobility/story.yaml:27` — first use of "xGB" (in
   the `gbm_vs_nn` caption): "xGB is best on test at −31.2%" → "xGB
   (XGBoost) is best on test at −31.2%". No other edit to that line. The
   later definition at line 190 ("xGB is XGBoost, and LightGBM is another")
   left as instructed; predeclared labels (`xGB versus naive` at
   `story.yaml:205`), metric keys, and all other uses unchanged.
2. `docs/projects/07-open-data-mobility.md:38` — first use on the page
   (verified nothing earlier defines it): "the xGB challenger" → "the xGB
   (XGBoost) challenger".
3. `projects/09-agentic-workflows/DESIGN.md` — inserted directly after the
   line containing "(8 unplanned calls)", as a new continuation line inside
   the same 2026-10-18 bullet, exactly as mandated:
   `Correction (2026-11-19): the "8 unplanned calls" count has no committed
   artifact behind it and is removed from the public copy; this record is
   kept for design history.`

No numbers, labels, keys, JSON, or figures changed. `short_version` did not
change (the 07 edit is in a caption, not the short copy), so `storyShort.ts`
needed no regeneration — confirmed by `--check`.

## Gates (actual output)

- `uv run python scripts/lint_story_language.py` →
  `lint-story-language: 13 stories — 0 errors, 0 warnings`
- `uv run python scripts/check_docs.py` → `check-docs: OK`
- `uv run python scripts/check_short_copy.py --check` →
  `short copy is single-sourced (39 surfaces across 13 stories)`
- `uv run python scripts/gen_story_short.py --check` →
  `story short map is current (.../storyShort.ts)`
- `uv run python scripts/check_headline_numbers.py` →
  `headline-numbers: OK (no unknown drift)`
- Web: `npm test` → `Test Files 56 passed (56)`, `Tests 753 passed (753)`;
  `npm run lint` → clean; `npm run build` → `✓ built in 12.72s`
- `uv run pytest -q projects/07-open-data-mobility` — **not run**: no file
  under the project's `src/` or `tests/` changed (per the handoff, expected
  no run).

## Notes

- Stop conditions did not trigger: the first-use definition required no
  predeclared-label change, and no headline number moved.
- The two deferred minor items from the execution review are now closed with
  the owner's decisions recorded in the handoff.
- **Placement fix (2026-11-19, per
  `04-fix-correction-placement.md`):** the correction sentence was first
  inserted directly after the "(8 unplanned calls)" line as the handoff
  literally instructed, which split the original sentence; it now sits at the
  **end of the 2026-10-18 bullet** with the same text and indentation.
  `git diff` on `DESIGN.md` shows exactly one added line; the original
  sentence reads unbroken. Gate re-run: `check-docs: OK`.
