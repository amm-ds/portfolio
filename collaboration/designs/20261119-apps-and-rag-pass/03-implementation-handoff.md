# Implementation handoff: apps and RAG improvement pass

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-19): steps 1–3 of `00-proposal.md`; in-process rate limiting; hosted spend for R2 and R3 under ONE combined cap of $3 total on `kimi-for-coding`, stop at $2.50.
Source design: `collaboration/designs/20261119-apps-and-rag-pass/00-proposal.md`

## Objective

Raise production readiness and code quality of `apps/agent-chat` and `apps/document-intelligence`, and refine the measured quality of `projects/01-rag-agent`, without changing any headline number in copy until the owner reads the report.

## Standing rules

- Branch `apps-rag-pass-2026-11-19` from `main`. Commit each step separately, each commit ending with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream tracking. Do not merge to `main`. Do not deploy.
- Hosted model calls: R2 and R3 only, sharing ONE cap of $3 total on `kimi-for-coding`. Stop at $2.50 and report. If R3's run would push the total past $2.50, run R2 only and hold R3 (report it).
- No new dependencies. No upgrades of existing dependencies. If a finding can only be fixed by an upgrade, stop and report it.
- No edits to committed records or existing reports. Write new files only, except for the source fixes in steps 4–6.
- No changes to `.env`, permissions, deployment files or CI configuration, except the rate-limit wiring and tests.
- Do not change any headline number in copy or cards.

## Step 1: read-only audit (no code changes)

Write `collaboration/reviews/20261119-apps-rag-pass-audit/00-audit.md` with:
- dependency audit of each app's `uv.lock` (use the tool already configured in the repo; if none is configured, say so and do not install one);
- coverage per app: run each app's tests with coverage and record the number (the floor is set to that measured value in step 6);
- `ruff` and `mypy` on each app's `src/`: list findings, marking each as real bug, style, or false positive;
- error response shapes: list each API error path and its response body, and whether any stack trace can reach a client;
- health and readiness: list the endpoints and the compose healthcheck target for each app.

Stop after the audit and commit it, so the owner can read it before fixes. Then continue to step 2 without waiting, unless step 1 finds a stop condition below.

## Step 2: real bugs from the audit

Fix only findings marked "real bug" in step 1, with a test that fails before the fix and passes after. Do not restyle code.

## Step 3: in-process rate limiting (both apps)

- Limit the paid endpoints: agent-chat chat and upload endpoints; document-intelligence upload and analysis endpoints. Identify the exact routes from the code.
- Key the limit on the authenticated principal (the `X-API-Key` in agent-chat; the `Principal` in document-intelligence). Unauthenticated requests are rejected by the existing auth before the limiter runs.
- In-process limiter only, using a fixed or sliding window in memory. Make the limit and window configurable through the app's existing settings module. Defaults: 30 requests per minute per key. Document in the app README that the limit is per process and not shared across replicas.
- Tests: a test that the N+1th request in the window returns 429 with a `Retry-After` header; a test that a different key is not limited; a test that the window resets.

## Step 4: health, readiness and error shape (both apps)

- Confirm `/health` and `/ready` exist. If one is missing, add it with a test.
- Confirm compose healthchecks target `/ready` (or `/health` if `/ready` does not exist). Fix the compose file only if the target is wrong.
- Add or confirm tests that API errors return a consistent JSON shape and that no traceback or internal path reaches a client.

## Step 5: coverage floor and lint (both apps)

- Set the coverage floor in each app's pytest configuration to the number measured in step 1, rounded down to one decimal. Do not set a higher number.
- Fix only the real bugs from the `ruff` and `mypy` findings (step 2). Leave style findings unchanged.

## Step 6: RAG offline refinements (project 01)

R4, retrieval baseline (offline):
- Compare the current retriever with BM25 on the committed sealed set. Report recall@5 with a 95% interval for each retriever.
- Output: NEW files `projects/01-rag-agent/reports/retrieval_baseline/` (metrics.json and report.md).

R5, error budget (offline, from committed metrics only):
- Produce one table with cost per query, latency median and p95, and the unsupported rate with its interval, side by side.
- Output: NEW file `projects/01-rag-agent/reports/error_budget/report.md` and its metrics.json. Do not change copy.

## Step 7: R2 warrant-strength check (hosted, shares the $3 cap)

- A three-level judge (supports, overstates, does not support) on the sealed set, `kimi-for-coding` only.
- Report the overstatement rate separately from the unsupported rate, each with a 95% interval.
- Output: NEW files `projects/01-rag-agent/reports/warrant_check/`. Record spend per run.
- Do not change the verify-on copy. Report the result to the owner.

## Step 8: R3 new sealed set (hosted, shares the same $3 cap)

- Build a new sealed set of 100 or more questions from the committed corpus. Fix it before any run; commit the set and its hash before the run.
- Run the existing evaluation once on the new set. Record spend.
- Output: NEW files `projects/01-rag-agent/reports/sealed_v2/`. Do not overwrite the existing sealed-set reports.
- Run R3 only if the combined spend so far stays under $2.50 after R2. Otherwise hold R3 and report it.

## Gates

After each step, run the gates for what changed. Report the actual output.

- apps: each app's `uv run pytest -q` with coverage, `ruff check`, `ruff format --check`, `mypy` on `src/`.
- project 01: `uv run pytest -q projects/01-rag-agent`, `ruff`, `mypy`.
- Repo: `scripts/check_docs.py`, `scripts/check_headline_numbers.py`.
- Web gates only if web code changes.

## Stop conditions

- A fix would change a committed record or a headline number: stop and write `OPEN_QUESTIONS.md` beside this handoff.
- A hosted call not listed here: stop.
- Combined hosted spend would exceed $2.50 before R3 completes: hold R3 and report.
- A dependency upgrade is needed: stop and report.

## Report

Write `collaboration/reviews/20261119-apps-rag-pass-report/00-report.md` with:
- one row per step: status, files changed, commands run, gate output as actually run, open questions;
- every number reported, with its source file;
- hosted spend per run and the total;
- commit hashes and the push result.

Do not claim a gate passed unless you ran it.
