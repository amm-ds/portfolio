# 09 Agentic workflows: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Legacy (run once per task): 15/15 fixed, 13/13 unseen answers, 5/6 refusals, 18/19 steps, 12/19 latency; about $0.13 per tuning suite. Live 2026-11-19: 13/13 answers, 6/6 refusals, 19/19 budgets; 52 captured calls all planned; deterministic graders (four code checks per answer task). Source: `projects/09-agentic-workflows/story.yaml`; metrics `projects/09-agentic-workflows/reports/metrics.json`.
- Single run per task; h19 is a guard error, so the 6/6 refusals score overstates the contract (2026-11-19 gap analysis; I did not re-derive it).
- Roadmap "next": multi-trial reliability (k>=3) behind an owner-approved cap.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | tau-bench introduces pass^k, reliability over k trials; gpt-4o-class agents succeed on under 50% of tasks and pass^8 is under 25% in retail. Our results are single runs. | SB | S03 |
| G2 | Anthropic's agent-eval guidance: pass@k (at least one success) vs pass^k (all trials succeed); multiple trials per task; code, model and human graders; read transcripts; capability vs regression evals. Our code-grader design matches the first; no multi-trial run. | SB | S05 |
| G3 | tau2-bench adds a dual-control telecom domain; best assistants succeed on 34-49% of the new tasks (ICML lay summary). Different domain; context only. | SEC | S50 |
| G4 | With 13 or 19 tasks, single-run pass rates have wide intervals (Wilson); no committed CI on the live counts found in story copy. | GAP (no committed interval) | none |

## Candidate improvements
**A. Multi-trial live run, k=3, report pass^1 and pass^3 with Wilson intervals.**
- Method: run the 19 held-out tasks three times; grade with the existing deterministic graders; report per-task and aggregate pass^k and compare to the single-run counts. New output file; existing live record untouched.
- Reference: https://arxiv.org/abs/2406.12045 (S03); https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents (S05).
- Cost: hosted calls under an owner-approved cap. The earlier gap analysis estimated about $0.28 at the observed rate and suggested a $5 cap; I did not verify those figures, so treat as inherited.
- Stop condition: cap reached, or any grader error rate above 1 task per run (fix the guard first, as with h19).

**B. Offline stochasticity probe with recorded transcripts.**
- Method: replay committed run records through the graders with grader perturbations (the check that a grader rejects a valid answer, per S05's "read transcripts" point); no hosted calls.
- Reference: S05.
- Cost: compute only, under 1 day.
- Stop condition: no recorded transcripts for the live run.

**C. Fix-forward on h19 and report refusals both ways.**
- Method: report refusals with and without h19 until the guard error is resolved; do not edit the committed record.
- Reference: S05 (grader fairness).
- Cost: none.
- Stop condition: owner decides the record wording (existing decision area).

**D. Add one dual-control or tool-error-injection task family later.**
- Method: tool failures injected at set rates; measure typed-outcome behaviour.
- Reference: https://arxiv.org/pdf/2506.07982 (S50).
- Cost: engineering plus hosted calls.
- Stop condition: A shows pass^3 close to pass^1, so extra families are lower value.

## Ranked recommendation
1. A (pass^k, hosted, capped): the most informative agent claim available.
2. B (grader audit offline): cheap.
3. C (dual reporting).
4. D (later).

## Queries used (standard, 2026-11-18)
- "tau-bench pass^k reliability tool-agent-user benchmark Sierra paper"
- "agent evaluation best practices multiple trials pass@k pass^k graders transcripts Anthropic demystifying evals for AI agents"
- "tau2-bench dual-control telecom agent benchmark arXiv"
- Fetched: arxiv.org/abs/2406.12045; anthropic.com/engineering/demystifying-evals-for-ai-agents.
