# Implementation handoff: next round (Q4a, Q4b, 15 document-intelligence sample)

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-19) for items 1, 3 and 4 only. Item 2 (RAG verify-on, Q3b) is NOT approved and is not part of this handoff.
Source design: `collaboration/designs/20261119-next-steps/00-next-steps.md`

## Objective

Run three bounded items, each writing NEW files only, and report the results. Do not change any headline number in copy until the report is read by the owner.

## Standing rules

- No git mutations except what is listed under "Commit and push". Commit on the branch `next-round-2026-11-19` created from `main`. Do not commit to `main`, do not force-push, do not deploy.
- Hosted model calls: only item 3, capped at $3 total on `kimi-for-coding`. Stop at $2.50 and report. No other hosted calls.
- No change to committed records. Write new report files; never overwrite an existing `metrics.json`, `report.md`, or `reports/*.json`.
- No full M5 rerun. No changes to `.env`, permissions or config. No downloads of datasets beyond what is listed.
- Do not start Q3b, Q3c, or any Q4 item other than the ones listed here.

## Item 1: Q4a, uplift single protocol (project 10)

Compute only, on the committed folds.

- Learners: causal forest, T-learner, X-learner, two-model learner.
- Metrics: Qini (unnormalised; state the formula beside the number) and AUUC (same quantity, labelled as in the design doc), each with an interval, and DR policy value across budgets.
- Output: NEW files `projects/10-uplift-experimentation/reports/single_protocol/` (metrics.json and a short report.md). Do not edit `reports/metrics.json`.
- Use the project's existing fold definitions; do not redefine folds.
- Gates: `uv run pytest -q projects/10-uplift-experimentation`, `ruff check` and `mypy` on the new code, `uv run python scripts/check_headline_numbers.py`.
- Stop: if a result would change a headline number in copy, stop and write `OPEN_QUESTIONS.md` beside this handoff. Do not edit copy.

## Item 2: RAG verify-on claim (project 01), copy change only

APPROVED: soften the copy to the measured judge error. No hosted calls. Q3b stays pending.

- Measured from `projects/01-rag-agent/reports/judge_calibration_report.json` (Q3a, offline): the local judge (qwen2.5:3b) accepts 0.4433 of unsupported claims, Wilson 95% [0.3752, 0.5136], kappa 0.5464. The hosted judge (qwen3:4b, committed predictions) accepts 0.3966 of unsupported claims under the strict count, kappa 0.6052 [0.5262, 0.6831]. Quote these with their intervals.
- Do not quote the hosted committed aggregate (FA 0.4536) next to the predictions-based figures. The report says they do not reconcile.
- Find every surface that states or implies the verify-on check catches unsupported claims (`git grep -n -i "verify" -- projects/01-rag-agent apps/showcase-web/src docs/projects/01-rag-agent.md`). Rewrite each so it says what the check does and how often its judges miss unsupported claims, with the intervals above.
- Do not change any headline number, the sealed-set result, or the cost figure.
- Gates: `uv run python scripts/lint_story_language.py`, `check_docs.py`, `check_short_copy.py --check`, `gen_story_short.py --check`, `check_headline_numbers.py`, and the web gates if `storyShort.ts` changes.
- Stop: if a surface claims a number not in the calibration report, stop and report it instead of editing.

## Item 3: document-intelligence sample (project 15)

Add documents to the existing set, then re-run the committed live metrics. This item makes hosted calls.

- Add 7 documents or more to the existing synthetic set, under `apps/document-intelligence/` fixtures. Keep them synthetic; do not use real personal data.
- Run the live evaluation on the expanded set with `kimi-for-coding` only, capped at $3 total. Record the spend per run in the report. Stop at $2.50.
- Output: NEW files `apps/document-intelligence/reports/expanded-<date>/` (metrics and report). Do not overwrite `reports/live-metrics.json`.
- Report entity F1 on the original set and the expanded set side by side, with intervals. Do not change the card or article copy.
- Gates: the app's own tests (`uv run pytest -q apps/document-intelligence`), `check_docs.py`.
- Stop: if the expanded set changes the original headline by more than the interval, stop and write `OPEN_QUESTIONS.md`.

## Item 4: Q4b, AG News risk-coverage (project 04)

Compute only, on the fresh holdout.

- Compute the risk-coverage curve and AURC for the transformer model on the fresh holdout.
- Output: NEW files `projects/04-nlp-classification/reports/risk_coverage/` (metrics.json and a short report.md). Do not edit existing reports.
- Gates: `uv run pytest -q projects/04-nlp-classification`, `ruff check`, `mypy` on the new code, `check_headline_numbers.py`.
- Stop: if a result would change a headline number in copy, stop and write `OPEN_QUESTIONS.md`.

## Commit and push

- Branch: `next-round-2026-11-19` from `main`.
- One commit per item, each with the trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>` as the last line.
- Push the branch with upstream tracking. Do not merge to `main`.

## Report

Write `collaboration/reviews/20261119-next-round-report/00-report.md` with:
- one row per item: status, files, commands run, gate output as actually run, hosted spend, open questions;
- every number reported, with its source file;
- the commit hashes and push result.

Do not claim a gate passed unless you ran it.
