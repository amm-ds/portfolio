# Execution plan: portfolio next steps

Date: 2026-11-21
Designer: Claude Code
Executor: Kimi Code (all execution). Owner decisions are marked **[owner]**.
Status: owner approved the recommendations on 2026-11-21 (D1, D2, D4 as after Phase 0, D5 and D6 approved, D7 approved). D3 is NOT decided: S4 stays blocked until the owner identifies the project 02 edits.

## Current state (verified 2026-11-21)

- Project 01 (RAG): G4 held-out complete (62/62 real outcomes; pooled 120 = 28/120 unsupported, valid for the current configuration but built on the unbounded agent loop). Agent-loop bounds implemented and measured on `agent-loop-bounds-2026-11-20` (`9997411`): 17 budget-terminated rows, 16 of them correct under the old config. Judge figure 0.4433 still cited in copy; Phase 0 re-run approved 2026-11-20 but not started.
- Apps: `apps-rag-pass-2026-11-19` (`601bcbf`) pushed, not merged.
- Working tree: uncommitted project 02 M5 metric edits (cause unknown, owner to identify); designer folders untracked; G4 handoff modified.

## Decisions needed from the owner

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| D1 | Tool-call limit after the bounds measurement: keep 8, raise, or partial-answer design | Raise to 16 and re-measure, with the 17 budget-terminated rows counted as failures in the headline. Input ceiling (200k) still bounds cost. | Step 3 |
| D2 | Cap for the step 3 re-measure | About $1.2 hard, $1.0 stop (earlier 120-question run cost $1.13) | Step 3 |
| D3 | Project 02 M5 edits: which to keep, revert, or commit | Owner identifies the cause first; no Kimi action until then | Headline check |
| D4 | Copy: retire 0.4433 now, or after Phase 0 | After Phase 0 reports (the figure may reproduce) | Step 5 |
| D5 | Merge `apps-rag-pass-2026-11-19` to main | Merge after its step 5 coverage floor is approved | Apps close |
| D6 | Approve `pytest-cov` for apps coverage floor | Approve | Apps close |
| D7 | Commit the designer folders to a design branch | Yes, on a separate branch | Tidy-up |

## Steps

Each step names its handoff. Steps without a handoff need one before Kimi starts.

**S1. Hosted-call hygiene (Kimi, $0).** Stop the untracked `projects/01-rag-agent/.env` from reaching local runs: local runs set the endpoint explicitly to local. Record the step 6 hosted call (~$0.02) in the agent-loop report. No new hosted calls.
- Handoff: this plan (no separate handoff needed; it's a config and documentation change).
- Depends on: nothing. Blocks: S3, S4.

**S2. Phase 0 judge re-run (Kimi, $0, local).** Run as approved 2026-11-20: `calibrate_judge.py` twice, on Ollama digest `357c53fb…`, into `reports/judge_reproduction/run1` and `run2`. Stop if the digest differs. Write `collaboration/reviews/20261120-phase0-reconcile-report/00-report.md` with the decision branch that applied.
- Handoff: `collaboration/designs/20261120-rag-phase0-reconcile/03-implementation-handoff.md` (approved).
- Depends on: S1 (for the local-run setting). Blocks: S5.

**S3. Tool-call limit re-measure (Kimi, hosted, cap per D2).** Only after D1 and D2 are answered.
- Change `agent_tool_calls_limit` to the chosen value. Re-run the 120 sealed-v2 questions. Count budget-terminated rows as failures in the headline. Keep the 200k input ceiling and the 4M backstop.
- Report: unsupported and false-abstention rates with Wilson intervals, the paired comparison with the old bounds, budget-terminated count, and spend.
- Handoff: needs an amendment to `collaboration/designs/20261120-agent-loop-bounds/03-implementation-handoff.md` (I'll draft it once D1 and D2 are answered).
- Depends on: D1, D2, S1. Blocks: S5, S6.

**S4. Project 02 working tree (Kimi, $0; after D3).** Revert or commit per the owner's decision, then rerun `check_headline_numbers.py`. No edits to project 02 numbers without the owner's instruction.
- Depends on: D3. Blocks: any commit that runs the headline gate.

**S5. Copy update (Kimi, after owner approval of the text).** Replace or retire the 0.4433 citations in `projects/01-rag-agent/README.md` and `docs/projects/01-rag-agent.md` (and `story.yaml` if it cites it), using S2's result. State the 26% headline's denominator both ways. Use the S3 numbers only if S3 ran.
- Handoff: I'll draft the copy diff for owner approval before Kimi edits any copy.
- Depends on: S2, S3, D4. Blocks: nothing.

**S6. Phase 1 hand labels (owner labels, Kimi prepares).** Blinded sample of about 30 answers from the S3 traces: all unsupported, all empty, and about 15 correct, chosen with seed 42. Owner labels each claim as supported or unsupported. Score the rubric judge against the labels, report agreement and a prediction-powered estimate with an interval.
- Handoff: needed, drafted after S3.
- Depends on: S3. Blocks: a copy claim about judge reliability.

**S7. Apps branch (Kimi, after D5 and D6).** Run the apps coverage floor step with `pytest-cov` approved, then merge to main if D5 says so.
- Handoff: `collaboration/designs/20261119-apps-and-rag-pass/03-implementation-handoff.md` (step 5 still held).
- Depends on: D5, D6. Independent of the RAG chain.

**S8. Designer folders (Kimi, after D7).** Commit the untracked designer folders to a design branch. No merge.

## Order and parallelism

- Now, in parallel: S1 (Kimi), S2 after S1, S4 once D3 is answered, S7 once D5 and D6 are answered.
- After D1 and D2: S3 (needs S1).
- After S2 and S3 and D4: S5.
- After S3: S6 (owner labels; Kimi prepares the sample).

## Cost

- Hosted: S3 only, about $1.1 (cap per D2). Everything else is $0.
- Spend so far on project 01 held-out and bounds work: about $4.2 of hosted spend, against the $1.30 cap you first approved; you approved the higher caps afterwards.

## Stop conditions (all steps)

- Any hosted call outside S3: stop.
- A committed report or the 58/62 question files would change: stop.
- Digest, hash or parent-file mismatch: stop.
- Spend reaches the step's stop figure: stop and report.
