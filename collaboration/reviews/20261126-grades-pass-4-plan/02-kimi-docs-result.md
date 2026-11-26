# Kimi docs handoff — result (02-kimi-docs-handoff.md)

Date: 2026-11-26. Branch: `wave8-articles-truthfulness-2026-11-25`.
Scope kept: documentation and reader-facing copy only; nothing committed or
staged by this task; no code, generators, metrics, or experiment outputs
touched; E9's in-flight 02 files (`cli.py`, `m5_full_refit.py`) untouched.

## Items

1. **09 overstated first-contact copy — DONE.** short_version now reads
   "A live hosted re-run passed 13/13 answers and 6/6 refusals; across five
   repeats, pass^5 = 17/19 within budget." (The "6/6 refusals" clause stays
   attached to the single first run, where it is true; the repeats sentence
   carries 17/19.) Same sentence in the `docs/projects/index.md` 09 cell,
   the root `README.md` 09 row, and the `docs/projects/09-agentic-workflows.md`
   opening blockquote (the short-copy gate requires all four surfaces).
   `storyShort.ts` regenerated via `scripts/gen_story_short.py` (repo rule).
   `projects/09-agentic-workflows/README.md` needed no edit: its 19/19 claim
   is dated to the 2026-11-19 run and is immediately followed by the
   pass^5 = 17/19 sentence.
2. **12 E4 disclosure — DONE (two stale clauses fixed).** The docs page
   (:81-82) and README (:87-88) already priced the variant (MAE 27.2
   [CI +0.6–+2.8], worse for the served MLP; LightGBM improves). Fixed the
   stale "correcting that mismatch needs a fresh run" clause in
   `README.md:86` and the same staleness in the story conclusions bullet
   (`story.yaml:326-330`), which now points at the priced sensitivity arm.
   No sentence implies the committed choice is robust to the variant; the
   headline is unchanged.
3. **01 E8 disclosure — CONFIRMED, no edit.** `story.yaml:209` and
   `docs/projects/01-rag-agent.md:193-197` already state all four points:
   local qwen2.5:3b, 95.9% of 147 committed claim labels (kappa 0.92),
   28/30 calibration, and that the answer-level re-grade was not done.
4. **02 demo sentence — DONE (wording only, numbers unchanged).**
   `README.md:107-108` no longer references the unpublished "sample curves"
   (figure dropped in Phase C, pending E9) and the run-on is split. All
   numbers (0.6161, 0.60/0.10/0.30, 0.6211, 0.95/0.00/0.05, 2 vs 9 origins,
   2016-05-22) unchanged; no refit result stated.
5. **13 "champion" check — CONFIRMED clean.** No occurrence in
   `docs/projects/13-model-serving.md`, the 13 README, or
   `projects/13-model-serving/story.yaml`. Config keys untouched.
6. **04 broken sentence — FOUND and FIXED.** `story.yaml:268-269` read
   "…compare the topic bars. Per-class F1 / The same Business and Sci/Tech
   blur…" (dangling fragment). Now: "…compare the topic bars. The same
   Business and Sci/Tech blur accounts for the residual per-class F1 gap."
7. **04 roadmap — CHECKED, reads complete.** 4 shipped + 1 next
   (scale response → full-data training → cascade → per-row persistence;
   next: calibrate the cascade gate). No stale reference to the dropped
   card. Card not restored, per instructions.

## Gates (exit codes, run after all edits)

- `lint_story_language.py` → 0 (0 errors, 1 pre-existing 02 warning that
  clears when E9 restores the eda figure)
- `check_short_copy.py --check` → 0 (42 surfaces)
- `gen_story_short.py --check` → 0 (regenerated once, see item 1)
- `gen_static_registry.py --check` → 0
- `check_headline_numbers.py` → 0 (24 claims, 0 findings)
- `check_docs.py` → 0
- `mkdocs build --strict` → 0
- `git diff --check` → 0

## Files changed (all docs/story copy)

- `projects/09-agentic-workflows/story.yaml` (short_version)
- `docs/projects/09-agentic-workflows.md` (opening blockquote)
- `docs/projects/index.md` (09 cell)
- `README.md` (09 row)
- `apps/showcase-web/src/lib/storyShort.ts` (regenerated, repo rule)
- `projects/12-tabular-ml-lifecycle/README.md` (stale clause)
- `projects/12-tabular-ml-lifecycle/story.yaml` (conclusions bullet)
- `projects/02-demand-forecasting/README.md` (demo sentence)
- `projects/04-nlp-classification/story.yaml` (broken sentence)

## Record-only notes (from the handoff's "not in scope")

- `13 model_serving/report.py` `_meta` dict literal: recorded; track before
  any 13 re-run.
- `04 dvc.yaml` cascade metrics declaration: recorded.
- Commit `5483124f`'s "uv.lock untouched per owner decision": the decision
  exists in the session record — the orchestrator's iteration-2 review
  (2026-11-26) instructed "Project 03 NAB scorer — avoid touching uv.lock…
  vendored as a small pure-Python module inside
  `projects/03-anomaly-detection/src/`". It was not written into a repo file
  before the commit; this note is the record.
- Final grade table will list 14 projects (01–13 and 15); noted.
- E10: per the owner's 2026-11-26 recommendation ("stop it"), no re-attempt
  will be made. E10 had already stopped itself at its re-measurement gate
  (+20.5%/+6.0% tok/s drift vs the 10% tolerance, Ollama 0.40.4→0.40.17,
  co-tenant load); the harness and gate evidence are committed (`c53069eb`).
  Nothing is running.
