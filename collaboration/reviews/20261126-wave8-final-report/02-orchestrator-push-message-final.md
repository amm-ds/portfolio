# Orchestrator message — commit, push and release Wave 8 to main and production

Reviews: Opus article report `00-report.md` (YES WITH NOTES); pre-push review `collaboration/reviews/20261126-wave8-prepush-review/00-prepush-review.md` (APPROVE WITH NOTES, no HOLD blockers). Owner decision: commit the uncommitted edits as a new commit on top of `ebb889cf`. Do not amend.

## Steps

1. Check the starting state:
   - Branch `wave8-articles-truthfulness-2026-11-25`.
   - `git rev-parse --short HEAD` is `ebb889cf`.
   - `git stash list` is empty.
   - Projects 01 and 15 have no diff against `c05accd0`.
   - `projects/08-inference-serving/data/bench_run_repeat.json` is not tracked and not staged.

2. Stage only the uncommitted edits (about 12 files): projects 02, 03, 13 story and README and DESIGN copy; `projects/13-model-serving/src/model_serving/report.py` (string literals only); `projects/13-model-serving/portfolio.yaml`; `projects/13-model-serving/reports/report.html` and `results.md`; `docs/projects/13-model-serving.md`; `apps/showcase-web/src/lib/staticRegistry.ts`; and the review folder `collaboration/reviews/20261126-wave8-final-report/`. Do not stage `.coverage`, `site/`, or any file under `data/` that is gitignored.

3. Re-run the cheap gates and record exit codes: `uv run python scripts/lint_story_language.py`, `check_short_copy.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `check_headline_numbers.py`, `check_docs.py`, `git diff --check`, `uv run mkdocs build --strict`. Also run `uv run pytest -q projects/13-model-serving/tests`. All must exit 0. The earlier full pytest, npm and mypy results are recorded in `collaboration/reviews/20261126-wave8-commit-handoff/00-commit-handoff.md`.

4. Commit as a new commit. Subject and body:

       docs(wave8): align project 13 copy and project 02 disclosure

       Replace the remaining "champion" wording in project 13 story, README,
       DESIGN, docs page, portfolio card, and the generated report headings
       with "served" or "selected" wording. Add one sentence to project 02
       explaining why the demo keeps the earlier blend and the article
       reports 0.95/0.00/0.05. Fix a run-on sentence in project 03.

       No numbers, claims or links changed. Report metadata files were
       restored to their committed bytes. No refit, benchmark or experiment
       was run.

   Do NOT add a `Co-Authored-By` model trailer.

5. Push the branch to origin.

6. Merge to `main` through the repo's normal path (PR or fast-forward, per the repo rules). Do not force-push and do not rewrite history.

7. Deploy to production with the repo's standard deploy process. If it is not documented in the repo, stop and report instead of guessing.

## Known notes (do not block the release)

Record these as follow-up items in the PR description or a tracking issue:
- **N1 (project 13):** `projects/13-model-serving/src/model_serving/report.py:147` still writes "Champion re-derivation". It appears in `reports/results.md` and `evaluation_metadata.json`. Changing it needs a deliberate metadata change.
- **N2 (project 12, already on main):** the docs page `docs/projects/12-tabular-ml-lifecycle.md` (lines 24, 61, 63), the report body and one figure axis still say "champion".
- **N3 (already on main):** review-process wording in `docs/projects/08-inference-serving.md:21` ("external audits") and `docs/projects/09-agentic-workflows.md:238` ("audit-P1 split").
- **N4:** the project 02 sentence appears in the README and in the long caption. Tighten to "each run scored it once" in a later pass.
- **N5:** `projects/02-demand-forecasting/src/demand_forecasting/m5_full_figures.py` hard-codes the earlier blend's values instead of reading them from the payload and metrics files.
- **N6:** commit `ebb889cf` says "conclusion order aligned to project 01", but only projects 03 and 12 follow that order. Do not amend; correct this in the PR description.

## Report back

The new commit hash, the `main` commit hash, the gate exit codes, the production deploy result, and any step that could not be completed.
