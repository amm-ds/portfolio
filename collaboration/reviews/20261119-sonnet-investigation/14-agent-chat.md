# 14 agent-chat app: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Lift-out chatbot-agent template on pydantic-ai, FastAPI, Postgres/pgvector (SQLite fallback); skills loaded from disk folders; HITL approval gate for `send_message`; scripted fake model for deterministic tests; a 16-case pydantic-evals suite (graders AnswerKeywords, ToolChoiceExact, CitationsWhenGrounded). Source: `apps/agent-chat/README.md`.
- Recorded eval reports in `apps/agent-chat/reports/`: fake model (`evals.md`, 33 grader rows all pass in the lines I counted), `evals-kimi-for-coding.md` "Passed 108/108 grader assertions", `evals-kimi-k3.1-pro.md` "Passed 24/33", `evals-kimi-k3-256k.md` "Passed 26/33"; plus focused reports (refund, SLA, handbook updates, refuse financial action, refuse missing tool, send-message denied). The 108/108 denominator differs from the 33 of the other reports; I did not establish why (more trials or more cases). Treat the denominator as unexplained until checked.
- No committed multi-trial reliability number; no committed claim-level groundedness score on cited answers.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | Agent evals: multiple trials per task; pass@k vs pass^k; mix code, model and human graders; read transcripts; separate capability and regression suites. | SB | S05 |
| G2 | pass^k reliability metric from tau-bench. | SB | S03 |
| G3 | pydantic-evals offers LLMJudge and prebuilt RAG rubrics (Ragas-style faithfulness, answer relevance), per-case evaluators and score-range checks. The suite uses deterministic graders only. | SEC | S51 |
| G4 | Citation quality: ALCE defines citation recall and precision with an NLI model, reporting 85.1% / 77.6% agreement with human judgments; the best model on ELI5 had 49% of generations lacking complete citation support. `CitationsWhenGrounded` checks presence of citations, not support. | SEC | S48 |
| G5 | Dual-control or user-in-the-loop evaluation (tau2-bench). Out of scope for a template unless users act in the environment. | SEC | S50 |

## Candidate improvements
**A. Multi-trial run of the 16-case suite on a hosted model: pass^k with k=3.**
- Method: run each case three times; report per-case pass^3 and aggregate; keep the fake-model run as the CI regression suite; flag cases whose result differs across trials. Explain the 108 vs 33 denominators in the report header.
- Reference: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents (S05); https://arxiv.org/abs/2406.12045 (S03).
- Cost: hosted calls under an owner cap (16 cases x 3; per-call cost not in committed files for this app, so no figure here).
- Stop condition: cap reached; or two cases are flaky because of grader brittleness, in which case fix the grader first.

**B. Citation-support grader (offline NLI) beside `CitationsWhenGrounded`.**
- Method: add a grader that checks each citation's source passage entails the cited sentence, using a small local NLI/fact-check model; report citation recall and precision as in ALCE; keep existing graders untouched.
- Reference: https://arxiv.org/pdf/2305.14627 (S48); https://arxiv.org/html/2404.10774v2 (S52).
- Cost: compute only, about 1-2 days; model download needs owner OK.
- Stop condition: the NLI grader disagrees with hand labels on more than 20% of a 30-item check; drop it.

**C. Failure triage on the Kimi k3.1-pro (24/33) and k3-256k (26/33) runs.**
- Method: read the transcripts for the failed cases; classify as agent mistake, grader rejecting a valid answer, or model-specific tool-format issue; report the split. Existing reports unchanged.
- Reference: S05 ("read transcripts").
- Cost: reading only.
- Stop condition: failures are all grader brittleness; then grader fixes are the handoff, not model changes.

**D. LLMJudge rubric for refusal quality on the two refusal cases.**
- Method: use pydantic-evals LLMJudge with a specific rubric; calibrate on 20 hand-labelled outputs before trusting.
- Reference: https://ai.pydantic.dev/evals/evaluators/overview (S51).
- Cost: hosted judge calls under a cap.
- Stop condition: judge agreement with hand labels below kappa 0.6 (convention, S09).

## Ranked recommendation
1. C (triage of failed cases): free and informative; unlocks grader fixes.
2. B (offline citation-support grader).
3. A (pass^k; hosted).
4. D.

## Queries used (standard, 2026-11-18)
- "agent evaluation best practices multiple trials pass@k pass^k graders transcripts Anthropic demystifying evals for AI agents"
- "pydantic-evals evaluators LLMJudge dataset evaluation framework documentation"
- "document question answering citation attribution evaluation ALCE citation precision recall PDF extraction benchmark OmniDocBench"
- "tau2-bench dual-control telecom agent benchmark arXiv"
