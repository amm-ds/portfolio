# Phase 0 reconcile report: the committed local-judge 0.4433 does not reproduce

Date: 2026-11-21
Handoff: `collaboration/designs/20261120-rag-phase0-reconcile/03-implementation-handoff.md`
(approved: local re-run only, $0 hosted)
Branch: `agent-loop-bounds-2026-11-20` (S2 of `20261121-execution-plan`).
Zero hosted calls; Ollama only.

## Setup

- Script: `projects/01-rag-agent/scripts/calibrate_judge.py` at commit-tree
  `2645819` (style(01): format R8.1 scripts), run **unmodified** twice with
  `--model qwen2.5:3b --repeat 2` (the committed defaults otherwise).
- Ollama digest verified before running:
  `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b` — matches
  the handoff value; stop condition clear.
- Code-path commit for both runs: `b6742bb` (S1 guard; calibrate_judge forces
  local via `Settings` kwargs, so the guard is belt-and-braces here).
- Outputs: `reports/judge_reproduction/run1/` (`…T021057`) and
  `reports/judge_reproduction/run2/` (`…T022152`), relocated unmodified from
  the script's timestamped folders. Each run judged the 194 claims twice
  (2 passes) plus the answer-level block; rates below use the script's own
  scoring (10 `manual_review` rows excluded from rates, n=184, as committed).

## Results

Committed record under test: FA 0.4433, documented as 86/194 (all-claims
denominator).

| run | pass | FA strict (unsupported only) | FA all-claims (denominator 194) | FR | kappa |
|---|---|---|---|---|---|
| run1 | 0 | 0/87 = 0.0000 [0.0000, 0.0423] | **0/194 = 0.0000 [0.0000, 0.0194]** | 0.8144 | 0.1773 |
| run1 | 1 | 1/87 = 0.0115 [0.0020, 0.0623] | **1/194 = 0.0052 [0.0009, 0.0286]** | — | — |
| run2 | 0 | 0/87 = 0.0000 [0.0000, 0.0423] | **0/194 = 0.0000 [0.0000, 0.0194]** | 0.7732 | 0.2172 |
| run2 | 1 | 0/87 = 0.0000 [0.0000, 0.0423] | **0/194 = 0.0000 [0.0000, 0.0194]** | — | — |

Run-to-run spread: pass-0 0 vs 0; pass-1 1 vs 0 — within ±2 claims.
Repeat flip rates: 0.1141 (run1), 0.0978 (run2) — the judge is noisy but
the FA counts are stable at the decision scale.

## Decision branch (pre-registered)

- Reproduced (both runs within ±1 of 86/194): **no** — runs show 0 and 1
  accepted unsupported claims against 86.
- Nondeterministic (runs differ > 2 claims): **no** — spread ≤ 1.
- **Neither reproduces: the committed 0.4433 (86/194) is NOT reproducible in
  this environment.** This branch applies.

This is now the third non-reproduction of the figure: the reconciliation
entailment-prompt pass (2/194) and rubric-prompt pass (23/194), both
committed under `reports/verifier_reconciliation/`, and now the original
script itself, unchanged, twice, on the pinned digest: 0–1/194.

## Can the README/docs lines citing 0.4433 stay as they are?

**No.** The copy currently presents 0.4433 as the measured false-acceptance
of the local qwen2.5:3b judge. The original measurement pipeline, run
unchanged on the pinned model digest, produces 0.0000–0.0052 (all-claims
denominator) in both runs. Whatever produced 86/194 in the R7-era record is
not present in this environment (no digest/commit exists in that record to
compare against). The honest copy state is: the local judge's measured FA on
the 194-claim calibration set, as reproduced 2026-11-21, is 0/194 [0.0000,
0.0194] (run1 pass 0) with a false-rejection rate of 0.77–0.81 — i.e. the
current local judge is far stricter than the committed figure claimed, not
more lenient. Copy edits are S5 and wait for the owner's approved text; this
report supplies the numbers.

## Gates (actual output)

- `uv run python scripts/check_headline_numbers.py` → `11 claims checked,
  2 finding(s)` — both findings are the external project-02 working-tree
  edits (S4 blocked, owner to identify); nothing in this step touched project
  02.
- `uv run python scripts/check_docs.py` → `check-docs: OK`.
- Pytest not required per the handoff (no code changes); the project-01
  suite was green at the S1 commit (219 passed, 0 failed).

## Stop conditions

None triggered: digest matched, zero hosted calls, only new folders
(`reports/judge_reproduction/`, this review) were written.
