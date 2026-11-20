# Implementation handoff: verifier cascade, DEV-only calibration

Date: 2026-11-20
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): offline DEV-only calibration, $0 hosted. Nothing else is approved.
Source design: `collaboration/designs/20261120-verifier-cascade-dev/01-design-brief.md`, `02-architecture-proposal.md`

## Objective

Choose a three-band verifier cascade on the DEV split only, by pre-registered cross-validation, then report one descriptive TEST reading. No hosted calls. No copy or headline changes.

## Standing rules

- Create branch `verifier-cascade-2026-11-20` from `verifier-challenger-2026-11-20` (head `c574680`). Do not commit to the challenger branch.
- Commit each step separately, each ending with the trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. Do not merge. Do not deploy.
- Zero hosted calls. Local Ollama `qwen2.5:3b` is the only model run. If Ollama is not running, stop and report.
- No new Python dependency. No new download.
- No edits to existing reports, label sets, split files, `golden_*.json`, copy, or cards. New files only, plus the harness module, script, and tests, and a `.gitignore` whitelist for the new report directory if needed.
- Do not touch TEST rows for any selection. TEST is read once, after the rule is applied.

## Step 1: freeze the rule (commit before scoring)

Write `projects/01-rag-agent/reports/verifier_cascade_dev/rule.md` containing:

1. Score source: `reports/verifier_challenger/predictions.jsonl` (MiniCheck score per claim). Record its sha256.
2. Split source: `data/calibration/verifier_split.json`, DEV rows only (96 claims). Record its sha256.
3. Grid: `t_lo` and `t_hi` from the sorted unique DEV MiniCheck scores, `t_lo < t_hi`. Record the function used to generate it.
4. Folds: stratified 5-fold over DEV by label, seed 42. Write the fold assignment to `reports/verifier_cascade_dev/folds.json` before scoring.
5. Qualifying rule: cross-validated DEV FA over unsupported claims `<= 0.10` AND cross-validated DEV FR over supported claims `<= 0.10`.
6. Selection among qualifying bands: lowest deferred share; ties to lower FA.
7. Deferred claims: scored by local `qwen2.5:3b` with the same prompt and parsing as the existing local judge in `src/rag_agent/judge.py`. Unparseable verdicts count as unsupported and are reported as a count.
8. No re-scan after results. No change to 4–7 after results.

Commit: `docs(01): verifier cascade - frozen DEV-only rule and folds, before scoring`. Record the rule file sha256 in the report.

## Step 2: local judge, all 194 claims, once

- Run `qwen2.5:3b` on all 194 claims in `data/calibration/claims.jsonl` with the existing local judge prompt. Cache verdicts to `reports/verifier_cascade_dev/local_verdicts.jsonl`.
- Record the Ollama model digest and the number of unparseable verdicts.
- The committed local aggregate has no per-claim verdicts, so this run is needed. Report agreement with the committed aggregate FA (0.4433) as a reconciliation check.
- Commit: `feat(01): verifier cascade - local judge verdicts cached for 194 claims`.

## Step 3: cascade code and tests

- Add `projects/01-rag-agent/src/rag_agent/verifier_cascade.py`: pure functions for decision per claim, grid generation, fold assignment, CV selection, and the final fit.
- Add `projects/01-rag-agent/scripts/verifier_cascade_dev.py` that writes `metrics.json`, `predictions.jsonl`, `report.md`.
- Tests: fold assignment disjoint and covers DEV; decision function returns accept at `s >= t_hi`, reject at `s <= t_lo`, defer otherwise; selection function accepts only DEV rows (assert the input contains no TEST ids); grid has `t_lo < t_hi`.
- Commit: `feat(01): verifier cascade harness and tests`.

## Step 4: CV selection and final fit (DEV only)

- Run CV selection on DEV. Record per-band CV FA, CV FR, deferred share.
- Select the qualifying band by the rule. If none qualifies, record "no qualifying band" and skip Step 5's fit; still write the report.
- Fit the chosen band on full DEV and record the final `(t_lo, t_hi)`.
- Commit: `feat(01): verifier cascade - DEV CV selection and final fit`.

## Step 5: one descriptive TEST reading

- Only if Step 4 found a qualifying band: apply the final `(t_lo, t_hi)` to TEST once.
- Report TEST FA, FR, deferred share, with Wilson 95% intervals. Label it "second use of TEST; descriptive; not used for selection".
- If no qualifying band was found, do not read TEST; report that TEST was not used.
- Commit: `feat(01): verifier cascade - TEST descriptive reading`.

## Gates

Run and report actual output:

- `uv run pytest -q projects/01-rag-agent`
- `uv run ruff check` and `uv run ruff format --check` on the new files
- `uv run mypy projects/01-rag-agent/src projects/01-rag-agent/scripts`
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`

Do not claim a gate passed unless you ran it. The RAG suite coverage gate was failing before this work (78.19% against 80%); report the suite result and the coverage number separately, and do not change the threshold.

## Stop conditions

- Ollama not running or `qwen2.5:3b` not available: stop and report.
- Any hosted call: stop.
- Rule or folds need changing after scoring started: stop and write `OPEN_QUESTIONS.md`.
- Result would change a headline number or copy: stop and report.

## Report

Write `collaboration/reviews/20261120-verifier-cascade-dev-report/00-report.md` with:
- commit hashes, push result;
- rule file sha256, folds sha256, predictions file sha256, Ollama digest;
- the grid size and CV results for every qualifying and non-qualifying band (summary table);
- chosen band and final thresholds, or "no qualifying band";
- TEST reading, labeled as second use, or "not read";
- unparseable verdict count and local-aggregate reconciliation;
- gate commands and actual output;
- explicit statement that no hosted calls were made;
- open questions.
