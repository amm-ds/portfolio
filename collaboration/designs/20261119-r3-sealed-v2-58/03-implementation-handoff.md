# Implementation handoff: R3 sealed-v2 pass, 58 questions

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-19): run 58 of the 120 questions in the committed sealed-v2 set, under the combined $3 cap on `kimi-for-coding`, stop at $2.50.
Branch: `apps-rag-pass-2026-11-19` (continue on it; do not create a new branch).
Source: `collaboration/reviews/20261119-apps-rag-pass-report/00-report.md` (R3 held), `collaboration/designs/20261119-apps-and-rag-pass/OPEN_QUESTIONS.md`.

## Objective

Run the existing verify-on evaluation once on a fixed 58-question subset of `projects/01-rag-agent/data/golden_sealed_v2.json`, and report the results as NEW files only.

## Standing rules

- Commit on `apps-rag-pass-2026-11-19`. Each commit ends with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push to the existing upstream. Do not merge to `main`. Do not deploy.
- Hosted calls: only the R3 run below, on `kimi-for-coding`. Combined spend with R2 ($0.394369, already recorded in `projects/01-rag-agent/reports/warrant_check/metrics.json`) must stay under $2.50 at all times. The run must not exceed $2.50 cumulative.
- No edits to committed records or existing reports. Do not overwrite `golden_sealed_v2.json`, `golden_sealed_v2.sha256.json`, or anything under `reports/` that already exists.
- No new or upgraded dependencies. No changes to `.env`, permissions, CI or deployment files.
- Do not change any headline number, card, or copy.

## Step 1: fix the subset before any run

- Rule (fixed here, not chosen after seeing results): take the entries of `golden_sealed_v2.json` at zero-based list indices 0, 2, 4, …, 114. That is 58 entries. Keep the original order.
- Write `projects/01-rag-agent/data/golden_sealed_v2_58.json` with exactly those 58 entries, unchanged.
- Write `projects/01-rag-agent/data/golden_sealed_v2_58.sha256.json` in the same shape as `golden_sealed_v2.sha256.json`: `file`, `sha256` of the subset file, `n_questions: 58`, `sealed_at_utc`, `source` (the parent file and its sha256 `616973ba390fdc1f8c9bf0b53fcf8e1b9bd24f5e93b563184bbc2ca9f8ce54e2`), `subset_rule` (the rule above), and `note`.
- Report the category mix of the subset (single_hop/multi_hop/unanswerable counts) against the full set's 68/24/28.
- Verify the parent file's sha256 still matches before writing.
- Commit the subset file and its manifest BEFORE the run: `feat(01): R3 58-question subset of sealed-v2, fixed and hashed before any run`.

## Step 2: run once

- Use the existing evaluate command with `--heldout`, `--heldout-file data/golden_sealed_v2_58.json`, and `--reports-dir reports/sealed_v2`. Check the exact command and flags with `--help` first. Verify-on, provider `kimi-for-coding` only, no `--ragas`, no `--max-questions`.
- Run it once. Do not re-run on failure without reporting first. If the run aborts at the spend ledger, keep the partial output, do not retry, and report.
- Record the spend the run reports, and the cumulative total with R2.

## Step 3: report files

Write NEW files under `projects/01-rag-agent/reports/sealed_v2/` (metrics.json and report.md, plus any traces the existing run writes). Use the same schema as `reports/error_budget` and `reports/warrant_check` where possible.

Include in report.md:
- n answered vs abstained, and the unsupported-claim rate with Wilson 95% interval, computed the same way as `reports/error_budget/metrics.json`.
- Spend for this run and cumulative with R2.
- The subset rule and sha256, so the run can be checked against the commit.
- A plain statement that the result is a 58-question subset, not the full 120, and what that does to the interval width.

Do not write copy or change any card.

## Gates

Run and report the actual output of each:

- `uv run pytest -q projects/01-rag-agent`
- `ruff check` and `ruff format --check` on changed files
- `mypy` on the changed files in `projects/01-rag-agent/src` and `scripts`
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`

Do not claim a gate passed unless you ran it.

## Stop conditions

- Subset or parent sha256 does not match: stop and report.
- The run would exceed $2.50 cumulative: the spend ledger stops it. Keep the partial output, report it, and make no further hosted call.
- A result would change a headline number or copy: stop and write `OPEN_QUESTIONS.md` beside this handoff.
- Any hosted call other than this run: stop.

## Report

Write `collaboration/reviews/20261119-r3-sealed-v2-58-report/00-report.md` with: subset commit hash and sha256; run commit hash; spend for the run and the cumulative total; n, abstain count, unsupported rate with Wilson interval; the gate commands and their actual output; push result. Note explicitly that the parent 120-question set and its sha256 were not changed.
