# Orchestrator message — evaluate and commit the grade-gap pass, then redeploy

Source report: `collaboration/reviews/20261126-grades-pass-2/00-pass.md` (verdict READY WITH LISTED GAPS). Only project 15 reaches a 9.0 overall. The rest are at 7.8 to 8.8, with the remaining gaps listed as needing experiments.

## State you will find

- Branch: `main`, HEAD `acf6f9f7` (the wave8 commit is already on main). Branch `wave8-articles-truthfulness-2026-11-25` is at the same commit.
- Working tree: about 64 uncommitted files from the grade-gap pass. No stash.
- Projects 01 and 15 may be edited in this pass (15 diagrams were added). Check each file before committing.

## Before committing

1. Read `00-pass.md` in full, especially the "Before you commit" section.
2. Check the stamp check. `stamp_metrics_meta.py --check` already fails at HEAD for projects 01, 02, 09 and 11, which were not touched in this pass. Decide whether to fix those separately or record them as known. Do not restamp them silently.
3. Restamp the one file this pass changed: `projects/12-tabular-ml-lifecycle/reports/metrics.json` (copy string "per owner decision 8"). Restamp it after the commit, as was done for project 15 in `07be7998`. Re-run `stamp_metrics_meta.py --check` for 12 only.

## Gates to run before committing (record exit codes)

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy libs projects apps`
- `uv run python scripts/lint_story_language.py`, `check_short_copy.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `gen_route_manifest.py --check`, `check_headline_numbers.py`, `check_docs.py`, `check_demo_contract.py`, `check_diagram_fences.py`
- `uv run mkdocs build --strict`, `git diff --check`
- `cd apps/showcase-web && npm test && npm run lint && npm run build`
- pytest for `scripts/tests`, projects 03, 08, 09, 10, 12, 13, 15, `libs/portfolio-core` and `apps/showcase-api`, run with `--no-cov`

Opus reports all of the above exit 0, except `stamp_metrics_meta --check`, which is red for the reasons above.

## Commit

Commit as a new commit on `main`, without amending and without a model co-author trailer:

    docs(portfolio): close grade gaps for projects 03, 08, 10, 12, 13, 15

    Fix figure subtitles and axes for 03, 08 and 12 through their generators;
    state the project 10 interval source and extend the headline check to it;
    add the five missing project 15 diagram specs and a fence check that fails
    on unregistered diagram ids; align review-process and "champion" wording;
    add project 04 to the headline check.

    No headline number changed. No experiment, refit or hosted call was run.
    Generated files were restored where a run rewrote metadata beyond the
    intended change.

## After committing

1. Redeploy the app from the new commit. `/health` should show the new sha.
2. Confirm the live project 13 and project 15 pages: no "champion" wording on 13, and no diagram placeholders on 15.
3. Restamp project 12 metrics after the commit (step 3 above), and commit that one-line change separately.

## Decisions for the owner (not part of this commit)

Listed in `00-pass.md` as NOT REACHABLE WITHOUT EXPERIMENTS: 01 technologies, 02 visualizations, 03 technologies, 04 technologies and results, 08 technologies, 09 technologies, 10 visualizations, 12 technologies. Each needs a compute or hosted-call budget decision first.

Also not done, because they are outside the allowed paths: shortening jargon in the root `README.md` (projects 01 and 09), and wiring `check_diagram_fences.py` into CI under `.github/`.

## Report back

New `main` commit hash, gate exit codes, the restamp commit hash, the redeploy result, and any step that could not be completed.
