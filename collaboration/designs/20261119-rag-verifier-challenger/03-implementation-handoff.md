# Implementation handoff: RAG grounding verifier challenger, Phase 1

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): Phase 1 only, including the download of the MiniCheck-FT5 checkpoint named in Step 0, subject to its license check. Phase 2 is NOT approved.
Source design: `collaboration/designs/20261119-rag-verifier-challenger/01-design-brief.md`, `02-architecture-proposal.md`

## Objective

Score the committed 194-claim calibration set with one grounding-trained verifier challenger, using a fixed dev/test split and a pre-registered gate. Report the result as NEW files only. No hosted calls. No changes to the agent, the verify loop, copy, or headline numbers.

## Standing rules

- Branch: create `verifier-challenger-2026-11-20` from `apps-rag-pass-2026-11-19` (current head, which includes the R3 work). Do not commit to `apps-rag-pass-2026-11-19`; the apps pass is not yet merged and this is separate work. Commit each step separately with the trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>` as the last line. Push with upstream. Do not merge to `main`. Do not deploy.
- No hosted model calls of any kind.
- Downloads: only the checkpoint named in "Step 0". Nothing else is fetched.
- No new Python dependency. If the checkpoint needs a package not already in `uv.lock`, stop and write `OPEN_QUESTIONS.md`.
- No edits to existing reports, label sets, `golden_*.json`, copy, or cards. New files only, plus the harness module and tests.
- Do not change `.env`, permissions, CI, or deployment files.

## Step 0: license and checkpoint check (owner approval required)

Before any download:

1. Confirm the checkpoint named by the owner: `MiniCheck-FT5` (770M, the checkpoint from Tang et al., EMNLP 2024). Record the source URL, license text, and download size.
2. If the license does not allow research or portfolio use, stop and use the second candidate only after owner approval: an NLI cross-encoder, named by the owner.
3. Record the license and source in `projects/01-rag-agent/reports/verifier_challenger/license.md`.

Stop and report if the owner's approval naming the checkpoint is not in this file.

## Step 1: fixed dev/test split (commit before any scoring)

- Read `projects/01-rag-agent/data/calibration/claims.jsonl` (194 claims; labels `supported` and `unsupported`; 97 each).
- Write `projects/01-rag-agent/data/calibration/verifier_split.json`: a stratified split by label, seed 42, 50% dev / 50% test. Record the seed, counts per label per split, and the sha256 of `claims.jsonl`.
- Assert in a test that dev and test are disjoint and cover all 194 ids.
- Commit: `feat(01): verifier challenger - fixed dev/test split of the calibration claims, before any scoring`.

## Step 2: adapter and harness

- Add `projects/01-rag-agent/src/rag_agent/verifier_challenger.py` with an adapter `score(claim, evidence) -> float` in `[0, 1]`, deterministic on CPU.
- Add a script `projects/01-rag-agent/scripts/verifier_challenger.py` that:
  1. loads the split and claims;
  2. scores the DEV set; chooses the threshold by the rule in "Gate" below; scores the TEST set once at that threshold;
  3. computes FA over unsupported claims (strict), false rejection over supported claims, and Wilson 95% intervals for each;
  4. re-scores the full 194 twice on CPU and reports the flip rate;
  5. writes `reports/verifier_challenger/{metrics.json, predictions.jsonl, report.md}`.
- Reuse the project's existing Wilson helper. Do not write a second one.
- Add tests: split disjointness and coverage; the threshold function reads DEV rows only (assert on the function's input); adapter output is in `[0, 1]`; the Wilson helper matches a known case.
- Commit: `feat(01): verifier challenger harness and tests`.

## Step 3: Phase 1 run (once)

- Run `uv run python scripts/verifier_challenger.py` once. Keep the output. Do not re-run with a different threshold or split. If the run fails, fix the code, not the gate, and report.
- Commit results: `feat(01): verifier challenger Phase 1 result (offline, $0 hosted)`.

## Gate (pre-registered; do not change after results)

Threshold rule: on DEV, choose the threshold that maximizes accuracy, with ties broken by the lower threshold. Record it.

Pass requires ALL of:

- TEST FA (strict, unsupported claims accepted): point estimate ≤ 0.25, AND Wilson 95% upper bound < 0.3269 (the lower bound of the committed hosted judge's strict interval, `judge_calibration_report.json`).
- TEST false rejection (supported claims rejected): point estimate ≤ 0.10.
- Flip rate across two CPU runs ≤ 0.05.

Report the result whether it passes or fails. A fail is a valid outcome and is reported as the finding.

## Baselines to report next to the challenger (same 194 claims; read from committed files only)

- local qwen2.5:3b: FA(strict, all claims) 0.4433 [0.3752, 0.5136] from `reports/judge_calibration/results.json` (committed aggregate, reconciles).
- hosted qwen3:4b: strict FA 0.3966 [0.3269, 0.4707], kappa 0.6052, from `reports/judge_calibration_hosted/.../predictions.jsonl`. Compute the strict figure from predictions, not the committed aggregate (0.4536 does not reconcile).

Note: these baselines are scored on all 194 claims. The challenger is scored on TEST (about 97 claims). Report the baselines on TEST too, computed from the predictions file, so the comparison uses the same claims.

## Gates

Run and report the actual output of each:

- `uv run pytest -q projects/01-rag-agent`
- `uv run ruff check projects/01-rag-agent` and `uv run ruff format --check` on the new files
- `uv run mypy projects/01-rag-agent/src projects/01-rag-agent/scripts`
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`

Do not claim a gate passed unless you ran it.

## Stop conditions

- Owner approval for the checkpoint is not in this file: stop.
- License does not allow the use: stop and report.
- Any hosted call: stop.
- Split or gate needs to change after results are seen: stop and write `OPEN_QUESTIONS.md`.
- Result would change a headline number or copy: stop and report. No copy edits in this handoff.

## Report

Write `collaboration/reviews/20261119-rag-verifier-challenger-report/00-report.md`:

- commit hashes and push result;
- checkpoint name, source, license, download size, sha256;
- split seed, counts, and file sha256;
- threshold chosen on DEV and its value;
- TEST results: challenger FA (strict) and Wilson 95%; false rejection and Wilson 95%; the same two numbers for both baselines on TEST; flip rate;
- gate result: pass or fail, criterion by criterion;
- the gate commands and their actual output;
- open questions; statement that no hosted calls were made.
