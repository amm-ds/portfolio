# Implementation handoff: reconcile the local judge gap (project 01)

Date: 2026-11-20
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): offline reconciliation check only. $0 hosted. Nothing else.
Source: `collaboration/reviews/20261120-verifier-cascade-dev-report/00-report.md` (reconciliation caveat), `projects/01-rag-agent/reports/judge_calibration/results.json` (committed FA 0.4433 for qwen2.5:3b)

## Objective

The cascade report found the local judge gives false acceptance 23/194 = 0.1186 with the rubric prompt, against a committed 0.4433 with the entailment prompt. The report called the gap "expected" from the prompt change. Nothing checks that. This handoff checks it by running both prompts through the same code path on the same 194 claims, and says whether the gap is the prompt or a bug.

## Standing rules

- Branch: `verifier-reconciliation-2026-11-20` from `verifier-cascade-2026-11-20` (head `113032e`). Commit each step with the trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. Do not merge. Do not deploy.
- Zero hosted calls. Only local Ollama `qwen2.5:3b` at `localhost:11434`. If Ollama is not running or the model is missing, stop and report.
- No new dependency, no new download.
- Do not edit existing reports, `local_verdicts.jsonl`, `rule.md`, `folds.json`, `cv_results.jsonl`, or any copy. Write new files only.
- Do not change any verdict in the existing cache. The check reads the cache; it does not replace it.

## Step 1: locate both prompts and both code paths

- The rubric prompt and 0.5 cut: `projects/01-rag-agent/src/rag_agent/judge.py`. The cascade run used this path.
- The strict entailment prompt: `calibrate_judge.py` (find it under `projects/01-rag-agent/scripts/` or the calibration module). This produced the committed 0.4433.
- Record the file, function, and prompt text hash for each. Do not paraphrase prompts; copy them verbatim into the report.
- Stop and report if the committed 0.4433 cannot be traced to a script in the repo.

## Step 2: run the entailment prompt through the cache path

- Score all 194 claims from `data/calibration/claims.jsonl` with the entailment prompt, using the same forced-local Ollama call and the same parsing used by the cascade run. Write to `projects/01-rag-agent/reports/verifier_reconciliation/entailment_verdicts.jsonl`.
- Record Ollama digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`, and confirm it matches before the run.
- Commit: `feat(01): reconciliation - entailment-prompt verdicts through the cascade code path`.

## Step 3: compare the two prompts on the same claims

Compute, for each prompt, over all 194 claims:
- false acceptance over all claims, with the committed denominator (194), and over unsupported claims only (97);
- false rejection over supported claims (97);
- Wilson 95% intervals for each.

Also report:
- agreement between the two prompts' verdicts (count and share);
- the 2×2 table of rubric verdict against entailment verdict, against the gold label.

Check reconciliation: the entailment-prompt FA over all 194 claims should equal the committed 0.4433 (86/194). Report whether it does.

Decision rule, fixed here before running:
- If the entailment-prompt FA reproduces 0.4433 (86/194, within 1 claim): the gap is the prompt. The cascade result stands for the rubric prompt; the committed local number is for the entailment prompt.
- If it does not reproduce (differs by more than 1 claim): the committed 0.4433 or the cache path is wrong. Report the discrepancy and stop. Do not change the cascade result.

## Step 4: report

Write `collaboration/reviews/20261120-verifier-reconciliation-report/00-report.md`:
- prompts, file paths, prompt hashes;
- Ollama digest, runtime, unparseable count per prompt;
- the table from Step 3 for both prompts;
- reconciliation result against 0.4433, and which decision branch applies;
- what this means for the cascade report's "expected" claim: confirmed, or not;
- gate commands and their actual output;
- explicit statement that zero hosted calls were made.

Gates: `uv run pytest -q projects/01-rag-agent`, `ruff check` and `ruff format --check` on new files, `mypy` on new scripts, `check_headline_numbers.py`, `check_docs.py`. The RAG suite coverage gate was already failing (78.19% against 80%); report that separately and do not change the threshold.

## Stop conditions

- Ollama or the model not available: stop.
- Any hosted call: stop.
- Entailment prompt not traceable to the committed 0.4433: stop and report.
- Result would change a headline number or copy: stop and report.
