# Implementation handoff: Phase 0, reproduce the committed local-judge figure

Date: 2026-11-20
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): local re-run only, $0 hosted. No copy edits.
Source: `collaboration/designs/20261120-rag-finish-plan/00-plan.md` (Phase 0)

## Objective

The committed local-judge false-acceptance figure 0.4433 (86/194) has not reproduced in two checks: 2/194 with the entailment prompt, and 23/194 with the rubric prompt. Re-run `calibrate_judge.py` unchanged, twice, on the same Ollama digest, to decide whether the committed figure is reproducible.

## Standing rules

- Branch `phase0-reconcile-2026-11-20` from `verifier-reconciliation-2026-11-20` (head `e7a4880`). Commit with trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. No merge, no deploy.
- Zero hosted calls. Only local Ollama `qwen2.5:3b` at `localhost:11434`. Stop if it is not running or the digest differs from `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
- Do not modify `calibrate_judge.py`, `judge.py`, any committed report, cache, or copy. Run the script as it is in the repo.
- No new dependency, no download.

## Steps

1. Record the git hash of `calibrate_judge.py` and the Ollama digest before running.
2. Run `calibrate_judge.py` as committed, run 1, writing to a NEW output folder `projects/01-rag-agent/reports/judge_reproduction/run1/`. Do not write to `reports/judge_calibration/`.
3. Repeat as run 2 into `reports/judge_reproduction/run2/`.
4. Compare each run's false acceptance (all 194 claims, denominator 194) with the committed 86/194 (0.4433). Also compare each run with the other.
5. Decision rule, fixed before running:
   - If both runs reproduce 86/194 within ±1 claim: the committed figure is reproducible. Report it as reproduced, with the script hash and Ollama digest.
   - If neither reproduces: the committed figure is not reproducible in this environment. Report it as unreproduced.
   - If the two runs differ from each other by more than 2 claims: the local judge is nondeterministic. Report the run-to-run spread as the finding.
6. Write `collaboration/reviews/20261120-phase0-reconcile-report/00-report.md` with: script hash, Ollama digest, runtime, both runs' counts and rates with Wilson 95%, the decision branch that applied, and whether the README and docs lines citing 0.4433 can stay as they are.

## Gates

- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`

Report actual output. Do not claim a gate passed unless you ran it. Pytest is not required for this phase because no code changes.

## Stop conditions

- Ollama or the model missing or a different digest: stop and report.
- Any hosted call: stop.
- Any file outside the new `reports/judge_reproduction/` and review folders would change: stop and report.
