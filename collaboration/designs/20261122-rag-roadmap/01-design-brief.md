# Design brief: RAG pipeline roadmap to target (project 01)

Date: 2026-11-22
Designer: Claude Code
Owner: session owner (portfolio repo)
Status: draft for owner review. Supersedes the "worth it" draft in `collaboration/designs/20261122-rag-reopen/01-design-brief.md` where they differ.

## Target (owner, 2026-11-22)

- Per-question F1 of **0.85 to 0.90** on the 120 sealed-v2 questions, with **zero errors** on that set.
- Excellent, reliable pipeline with SOTA practice as the use case.
- Each iteration's lift is measured and published on the experiment page.
- Nothing merges to `main` unless the iteration sets the results and is worth it.

## Metric (owner-chosen)

Per-question. Positive class = a fully correct answer:
- Answerable question: answered, every claim supported by a cited chunk, and the gold article cited.
- Unanswerable question: correct abstention.

Errors: unsupported claim, false abstention, wrong abstention (answering an unanswerable question), tool/schema/budget failure. Zero errors = zero per-question errors on the 120.

**Dependency:** this metric needs a judge that is trusted. The current hosted judge accepts about 40% of unsupported claims, so today's numbers cannot establish 0.85. The judge must be validated first (Iteration 0).

## Honest read of the target

Zero errors on 120 questions with a 40%-false-acceptance judge is not achievable to measure, and a strict 0.9 F1 on this corpus is a high bar. Expect the target to be reached in stages. Each stage is reported with its own lift, so the page shows progress even if the final target is not hit. If the target is not reached, the experiment stays open and the page says so.

## Data split (owner direction, 2026-11-22)

- **Dev holdout (refine against):** start small, drawn from the existing 65-question tuning set, first about 20 questions. Use it to iterate on each step until results are promising.
- **Grow gradually:** once a step is promising on dev, add questions in stages (for example 20, then 40, then all 65), re-checking the step's lift at each stage. Cheap steps first.
- **Sealed-120 stays untouched** until a final test of the chosen pipeline. Nothing is tuned against it.
- **Labels:** a Claude model (Sonnet, or Opus for a small sample) grades claims and labels questions. A small human-checked sample validates those labels. Checks that need no model (a claim must be an exact span of a retrieved chunk; cited ids must be retrieved) run on every answer.
- **Open models, larger allowed:** components may be open models of any size that fits the hardware and budget.

## Iteration ladder (sequential, one change per step, lift recorded)

Rule: each step keeps only changes that improve the primary metric with a CI that excludes zero, or that are required for correctness. Cheap retrieval checks run first. End-to-end runs with hosted calls happen only for candidates that pass the retrieval check.

| # | Step | Change | Measured by | Hosted cost |
|---|---|---|---|---|
| 0 | Baseline and judge | Validate judge on labelled claims (owner-labelled sample of about 150 claims, reviewed by owner); re-score the current hosted run on sealed-120 | Judge agreement with labels; baseline F1 with CI | Judge calls only |
| 1 | Data side | Audit the sealed questions and gold labels; fix mislabelled gold articles; check corpus quality and duplicates; document each change | Retrieval recall@k on fixed labels | None |
| 2 | Chunking | Compare 200/400/800 and overlap; then section-aware or semantic chunking | Recall@k, MRR, token cost (local, no LLM) | None |
| 3 | Embeddings | Compare MiniLM with stronger open embedding models (for example bge, e5, gte) on the chosen chunking | Recall@k, MRR (local) | None |
| 4 | Reranker | Compare the current cross-encoder with a stronger reranker; tune candidates kept | Recall@k after rerank, precision@k (local) | None |
| 5 | End-to-end | Run the best retrieval config through the agent on sealed-120 | Per-question F1, errors, CI | Full run, capped |
| 6 | Agent and budget | Raise tool-call limit to 16 with checkpointed saves; check budget terminations are zero | Budget terminations, F1 lift | Full run, capped |
| 7 | Verify and abstention | Tune repair/drop and the support floor; check the abstention gate on the 28 unanswerable | F1, false abstention, wrong abstention | Full run, capped |

Steps 2–4 are local and cheap. This is where most lift is expected to come from if the retrieval is the bottleneck. Step 5 onward costs hosted money.

## Per-iteration record (for the public page)

For each step, commit a row to `reports/experiment_log.json` on the working branch:
- change made (one line), config hash, commit;
- primary metric before and after, with CI;
- errors before and after;
- hosted spend and request hosts;
- kept or rejected, and why.

The public page shows this as a lift chart and a table, and states the judge's measured accuracy next to every F1.

## Merge rule

Nothing merges to `main` unless the iteration:
1. improves the primary metric with a CI that excludes zero (or is required for correctness), and
2. passes the reproducibility gate (command, config and traces committed; `check_headline_numbers.py` passes).

Rejected iterations stay on their branch and are recorded in the log, so the negative results are on the page too.

## Constraints

- Hosted spend per end-to-end run is capped (stop and hard cap set in that step's handoff). The current evidence: about $1.1 for the limit-8 run and $1.5–1.8 estimated for limit 16.
- No change to `src/` or copy without an approved handoff for that step.
- The G4 data branch stays unmerged until the owner approves.
- Project 02 metrics out of scope.

## Decisions needed from the owner

1. **Judge labels (step 0):** will you label about 150 claims, or should I draft labels for your review? Without validated labels, no F1 can be trusted.
2. **Approve the ladder order** (data, chunking, embeddings, reranker, end-to-end, agent, verify).
3. **Spend caps** per end-to-end run (current proposal: stop $2.50, hard $3.00 for the limit-16 run; same cap for the others unless you say otherwise).
4. **Embedding and reranker candidates** that are acceptable: open models only, or hosted options too?
