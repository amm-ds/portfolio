# Kimi handoff — documentation fixes from the grade pass 4 review

Source: Opus review of the grade pass 4 status (HOLD, 2026-11-26). Owner asked for the documentation items to proceed.

Scope: **documentation and reader-facing copy only.** Do not touch code, generators, metrics, or experiment outputs. Do not run experiments or hosted calls. Do not commit or push unless the owner asks; leave changes in the working tree.

Note on the working tree: it currently holds in-progress E9/E10 work for projects 02 and 08 (`projects/02-demand-forecasting/src/demand_forecasting/cli.py`, `m5_full_refit.py`, `projects/08-inference-serving/src/inference_serving/{cli.py,figures.py,quality.py}`). Do not edit or stage those files.

## Required fixes

1. **Project 09: first-contact copy overstates the run.** Both places say "all 19 tasks within budget" from the first run, but the repeated live runs found pass^5 = 17/19 (story.yaml:299, :344; docs page lines 10 and 169 already have the 17/19 figure).
   - `projects/09-agentic-workflows/story.yaml:2` (short_version): add the 17/19 pass^5 result in place of "all 19 tasks within budget".
   - `docs/projects/index.md:21` (09 row, Results cell): the same change.
   - Check `projects/09-agentic-workflows/README.md` for the same claim.
   - Keep the sentence short and in the house style. Do not add new numbers.

2. **Project 12: E4 result is not in the copy yet.** The corrected variant moved the served MLP by +1.73 MAE (CI +0.64 to +2.77), and LightGBM improved. This is disclosed in `projects/12-tabular-ml-lifecycle/story.yaml:289,354`. Check that the docs page `docs/projects/12-tabular-ml-lifecycle.md` and the 12 README say the same thing, and that no sentence still implies the committed model choice is robust to this variant. **Do not change the headline.** The owner has not yet decided on option B.

3. **Project 01: E8 disclosure.** The copy in `projects/01-rag-agent/story.yaml:209` and `docs/projects/01-rag-agent.md:193-197` says the answer-level 0.9091 is single-family. Confirm both say:
   - the second judge is a local 3B model (qwen2.5:3b);
   - it agrees with 95.9% of 147 committed claim labels (kappa 0.92);
   - it was calibrated at 28/30;
   - the answer-level re-grade has not been done.
   Wording only.

4. **Project 02: explanation sentence.** The README (`projects/02-demand-forecasting/README.md:108`) labels the demo as the earlier 0.6161 blend. Check the wording of the sentence about the earlier blend and the 0.6211 champion. Make no number changes. Status of the E9 refit is pending, so do not state a new refit result.

5. **Project 13: wording.** The reader-facing copy has no "champion". Check `docs/projects/13-model-serving.md`, the 13 README, and `projects/13-model-serving/story.yaml`. Leave the keys in `params.yaml` and `dvc.yaml` alone (they are config, not copy).

6. **Project 04: check the broken sentence.** The execution agent reported a sentence ("compare the topic bars. Per-class F1 / The same Business…") that reads as broken. Search `projects/04-*/story.yaml` and `docs/projects/04-*.md` for it. If it is there, fix it. If it is not, say so in the result file.

7. **Project 04 roadmap.** A redundant next-card was dropped in this pass. Check that the roadmap text still reads as complete. Flag any stale line; do not restore the card.

## Not in scope (record only, do not fix)

- `projects/13-model-serving/src/model_serving/report.py` still writes a `_meta` dict literal. This is code. Track it before project 13 is re-run.
- `projects/04-*/dvc.yaml` still declares a cascade metrics file the stage no longer writes. Config. Track it.
- Commit `5483124f` says "uv.lock untouched per owner decision". No such decision is recorded. Note this in the result file; do not amend.
- The final grade table must list **14 projects** (01–13 and 15). The brief says 15; there is no project 14.

## Open owner decision (do not act)

- E10 (project 08, quantization-matched pair) conflicts with the brief's decision 6. The owner has not yet said whether to stop it. Do not stop, start, or change any running process.

## Gates to run after editing

- `uv run python scripts/lint_story_language.py`
- `uv run python scripts/check_short_copy.py --check`
- `uv run python scripts/gen_story_short.py --check` (if story short versions changed, regenerate per repo rules and say so)
- `uv run python scripts/gen_static_registry.py --check`
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`
- `uv run mkdocs build --strict`
- `git diff --check`

Record exit codes in a result file: `collaboration/reviews/20261126-grades-pass-4-plan/02-kimi-docs-result.md`. List each file changed, each gate's exit code, and any item not done and why.

## Done means

- Items 1–5 done, item 6 either fixed or reported not found, item 7 checked.
- All gates above exit 0, or failures are reported with output.
- No file outside the documentation and story/short copy paths is modified.
