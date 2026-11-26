# Wave 8 — commit handoff for the orchestrator

Status: owner signed off on 2026-11-26 (project 02 fallback; item 53 closed). Design lane (Claude) has NOT committed. The orchestrator makes the commit.

Branch: `wave8-articles-truthfulness-2026-11-25`. Base HEAD: `c05accd0`. Do not push, merge or rebase.

## Before committing

1. Confirm HEAD is still `c05accd0`, and that `git stash list` is unchanged.
2. Done: the project 02 figures were regenerated offline with `build-figures-m5-full` (title date now 2016-05-22, no hand edit). Re-run `check_figure_axes`, `check_figure_budget`, `check_docs` before committing; all exited 0 on 2026-11-26.
3. Do NOT stage ignored or generated paths: `projects/08-inference-serving/data/bench_run_repeat.json` is gitignored and must stay uncommitted. Do not change `.gitignore`.
4. Do NOT touch projects 01 or 15. `git diff --stat c05accd0 -- projects/01-* projects/15-*` must be empty.

## Scope

Everything listed by `git status --short` on the Wave 8 tree: modified tracked files under `apps/`, `docs/`, `projects/02`–`13`, `README.md`, and the untracked review and design folders under `collaboration/` for 20261124, 20261125, 20261126 (wave8 round-3 article fixes, closeout, closeout-fixes, iteration final review, and this handoff).

Review folders are the audit record for the changes. Commit them with the change.

## Gate record (from the round-3 closeout and the iteration review)

All cheap gates exit 0 after the last edits: `lint_story_language.py` (0 errors, 0 warnings), `check_short_copy.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `check_headline_numbers.py`, `git diff --check`. Vitest on ForecastWorkbench, diagramSpecs and chartData 198/198; `tsc --noEmit` exit 0.

Not re-run after the final iteration: full pytest, npm build, mkdocs strict. Run them before committing if you want full evidence. Record the exit codes in the commit body or leave a note.

## Full gate record (run 2026-11-26 after the figure regeneration)

| Gate | Exit |
|---|---|
| `uv run ruff check .` | 0 |
| `uv run ruff format --check .` | 0 |
| `uv run mypy libs projects apps` | 0 |
| `uv run pytest -q --cov` | 0 (coverage 97.14%, required 80%) |
| `npm test` (apps/showcase-web) | 0 (56 files, 754 tests) |
| `npm run lint` | 0 |
| `npm run build` | 0 |
| `scripts/lint_story_language.py` | 0 (14 stories, 0 errors, 0 warnings) |
| `scripts/check_docs.py` | 0 |
| `scripts/check_short_copy.py --check` | 0 |
| `scripts/check_demo_contract.py` | 0 |
| `scripts/gen_static_registry.py --check` | 0 |
| `scripts/gen_story_short.py --check` | 0 |
| `scripts/gen_route_manifest.py --check` | 0 |
| `uv run mkdocs build --strict` | 0 |

## Commit message

Subject:

    docs(wave8): fix round-3 article truthfulness and demo labels

Body:

    Resolve round-3 Opus review findings for projects 02–13: transitions
    rewritten as full sentences, conclusion order aligned to project 01,
    figure and diagram claims corrected, and project 08 repeat-file claims
    removed (uncommitted observation only).

    Project 02: the demo keeps the earlier 0.6161 blend, labelled as the
    earlier blend, with the 0.6211 champion beside it. No catalog refit
    was run; owner signed off on this disclosure fallback.

    Project 02 figures were regenerated offline with build-figures-m5-full,
    so the sample-series title date now matches the committed origin.

    No experiments, refits or hosted calls. Projects 01 and 15 untouched.

Do NOT add a `Co-Authored-By` model trailer. The owner's rule is to omit model co-author lines from commits.

## After committing

Do not push or open a PR unless the owner asks. Report the new commit hash to the owner.
