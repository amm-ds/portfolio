# Implementation handoff: next round 2 (merge, then items 1–5)

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-19): merge `next-round-2026-11-19` into `main`; items 1–5 approved. Held items are NOT approved.
Source design: `collaboration/designs/20261119-next-round-2/00-proposal.md`

## Step 0: merge the previous round into main

1. `git fetch origin`. Confirm `origin/next-round-2026-11-19` is at `032bf34`. If not, stop and report.
2. Check out `main` and fast-forward it to `origin/main`.
3. Merge `next-round-2026-11-19` with a merge commit: `merge: next round 2026-11-19 (Q4a, RAG copy, DI sample, Q4b)`. Last line: `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`.
4. Push `main`. No force-push. If rejected, stop and report.
5. Do not delete the branch. Do not deploy. The production server stays on its current branch.

## Standing rules

- Commit round 2 work on a new branch `next-round-2-2026-11-19` created from the updated `main`. Do not commit to `main`.
- Hosted model calls: NONE in this round.
- No downloads, no new dependencies, no changes to `.env`, permissions or config.
- No edits to committed records or existing reports. Write new files only.
- Do not run Q3b, Q3c, Q4c, Q4d, Q4h, the 09 pass^k run, or the W3 provenance fix.
- Do not change any headline number in copy. Each result is reported to the owner first.

## Item 1: causal-forest label and stale DESIGN row (project 10)

- In `projects/10-uplift-experimentation/DESIGN.md`, find the "causal forests deferred" row. Replace it with a row stating that the single-protocol comparison used a hand-rolled cross-fitted DR-learner (sklearn only, no new dependency), with the result file `reports/single_protocol/`, and that a library causal forest remains out of scope.
- Copy: wherever project 10 copy names the model "causal forest", rename it to "DR-learner" with a one-clause definition. Run `git grep -n -i "causal forest" -- projects/10-uplift-experimentation apps/showcase-web/src docs/projects/10-uplift-experimentation.md` first.
- Gates: `check_docs.py`, `lint_story_language.py`, `check_short_copy.py --check`, `gen_story_short.py --check`, `check_headline_numbers.py`. Web gates only if `storyShort.ts` changes.

## Item 2: agent-chat failure triage (project 14 / apps/agent-chat)

- Read the failed cases behind the 24/33 (k3.1-pro) and 26/33 (k3-256k) runs from `apps/agent-chat/reports/` files.
- Group each failed assertion by cause (grader error, model error, tool error, other). Record the count per group.
- Output: NEW file `apps/agent-chat/reports/triage-2026-11-19.md`. Do not edit the evaluation reports.
- No model calls. Read committed files only.
- Stop: if a failure cannot be classified from the committed files, list it as unclassified. Do not guess.

## Item 3: rolling-origin MLP vs LightGBM (project 12)

- Compute check on the committed folds: does the MLP's tie with LightGBM hold across origins? Use the project's existing fold definitions; do not redefine folds.
- Output: NEW files `projects/12-tabular-ml-lifecycle/reports/rolling_origin/` (metrics.json, report.md). Do not edit `reports/metrics.json`.
- Report the difference per origin with an interval.
- Gates: `uv run pytest -q projects/12-tabular-ml-lifecycle`, `ruff check` and `mypy` on new code, `check_headline_numbers.py`.
- Stop: if a result would change a headline number, stop and write `OPEN_QUESTIONS.md` beside this handoff.

## Item 4: cold-start timings (project 11)

- Re-time cold starts with the existing harness and report per-cell spread, alongside the warm-only headline.
- Output: NEW files `projects/11-data-engineering/reports/cold_start/`. Do not edit existing timing reports.
- Gates: `uv run pytest -q projects/11-data-engineering`, `ruff check`, `mypy` on new code, `check_headline_numbers.py`.
- Stop: if the harness needs a new dependency or a download, stop and report.

## Item 5: open-loop arrival arm (project 13)

- Add a constant-arrival-rate arm to the existing load-test harness and compute p99 intervals from the raw records.
- Output: NEW files `projects/13-model-serving/reports/open_loop/`. Do not edit existing load reports.
- Gates: `uv run pytest -q projects/13-model-serving`, `ruff check`, `mypy` on new code, `check_headline_numbers.py`.
- Stop: if the arm changes an existing headline number, stop and report.

## Commit and push

- Branch `next-round-2-2026-11-19` from the updated `main`.
- One commit per item, each ending with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`.
- Push with upstream tracking. Do not merge to `main`. Do not deploy.

## Report

Write `collaboration/reviews/20261119-next-round-2-report/00-report.md`:
- Step 0 result: the merge commit hash and the push result.
- One row per item: status, files, commands run, gate output as actually run, open questions.
- Every number reported, with its source file.
- Hosted spend: must be $0.00.

Do not claim a gate passed unless you ran it.
