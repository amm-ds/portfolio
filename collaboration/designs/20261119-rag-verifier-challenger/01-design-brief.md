# Design brief: RAG grounding verifier challenger (project 01)

Date: 2026-11-19
Designer: Claude Code
Owner: amm-ds
Status: draft
Related artifacts: `projects/01-rag-agent/DESIGN.md` (§6 changelog 1.2.0, 1.2.1), `projects/01-rag-agent/reports/judge_calibration_report.json`, `projects/01-rag-agent/data/calibration/claims.jsonl`, `projects/01-rag-agent/reports/sealed_v2/`, `collaboration/reviews/20261119-apps-rag-pass-report/00-report.md`

## Problem

Project 01 is retrieval-strong and grounding-weak. The measured numbers:

- Retrieval: recall@5 0.831 on the 65-question tuning set (`reports/metrics.json`); recall@5 0.745 on the sealed set (README).
- Grounding: 26% of sealed answers still carry an unsupported claim (`reports/sealed_v2/metrics.json`, 15/58 = 0.2586, Wilson 95% [0.1635, 0.3838]); the earlier 55-question sealed pass had 9 of 55 (0.164).
- Verifier: the verify-on judges accept unsupported claims at a rate of about 40% (strict count, `judge_calibration_report.json`): local qwen2.5:3b 0.4433 [0.3752, 0.5136]; hosted qwen3:4b 0.3966 [0.3269, 0.4707] on committed predictions.

The copy already states these miss rates honestly. The weakest number in the project is therefore the verifier, not retrieval. Making the verifier stronger is the lever that could move a headline number.

## Context and evidence

| Claim or constraint | Evidence path | Why it matters |
|---|---|---|
| Retrieval changes have already been tested and do not clear the promotion gate: best tournament arm +1.5 pts recall@10 vs +5 pt gate | `projects/01-rag-agent/reports/retrieval_tournament/results.json`, DESIGN §6 1.1.0 | Retrieval swaps are low expected value; do not repeat them |
| A stricter LLM judge prompt (R8) traded unsupported claims for over-abstention (false abstention 0.05 → 0.25) | DESIGN §6 1.2.0 | Any verifier must be scored on false abstention too, not on false acceptance alone |
| Hosted judge calibration: FA 0.3966 strict on predictions; 0.4536 committed aggregate does not reconcile with predictions | `judge_calibration_report.json` | Baseline numbers must come from the predictions file, not the aggregate |
| A labeled claim set exists: 194 claims, 97 supported / 97 unsupported, each with evidence text | `projects/01-rag-agent/data/calibration/claims.jsonl` | Enables a free, offline verifier comparison |
| Per-claim verify evidence is committed for the sealed passes | `reports/citation_records_heldout.json`, `reports/sealed_v2/question_traces_heldout.json` | Enables offline replay of a new verifier on real answers, without hosted calls |
| Unused sealed questions remain: the 62 odd-indexed questions of `golden_sealed_v2.json` were not in the 58-question subset | `data/golden_sealed_v2.json`, `data/golden_sealed_v2_58.json` | A fresh confirmation set is available for any later end-to-end test |
| Grounding-trained verifiers outperform general LLM judges on grounding benchmarks at much smaller size | MiniCheck, Tang et al., EMNLP 2024 (arXiv 2404.10774): MiniCheck-FT5 (770M) reaches GPT-4-level accuracy on LLM-AggreFact and beats AlignScore by 4–10 pts | The strongest untested option for the verifier |
| ALCE defines citation precision and recall, scored with an NLI model, and reports Citation-F1 | ALCE, Gao et al. 2023 (arXiv 2305.14627) | Gives a field-standard citation metric the project does not yet report |
| ARES uses prediction-powered inference to tighten judge-error intervals using a small labeled set | ARES, Saad-Falcon & Khattab 2023 (arXiv 2311.09476) | Optional tighter intervals for the verifier's false acceptance |
| Contextual retrieval (LLM-written chunk context plus contextual BM25) cut retrieval failures 49% in Anthropic's test | anthropic.com/news/contextual-retrieval | Real gain, but retrieval is not the bottleneck here and it adds per-chunk hosted calls |

Caveat on the online sources: the MiniCheck figures above are from the 2024 paper. I did not check the current LLM-AggreFact leaderboard, and I did not check the model's license. Both must be checked before any download.

Caveat on the 194-claim set: the calibration judges were iterated against it (R7, R8), so it is not a clean holdout for a new verifier. The design below handles this with a fixed dev/test split.

## Goals and non-goals

Goals:

- Find out whether a grounding-trained verifier reduces the unsupported-claim acceptance rate below the current hosted judge, with an interval, without raising false rejection.
- Do it at zero hosted cost, on CPU, with pre-registered gates.
- If it passes, measure its effect on the committed sealed answers offline, and report ALCE-style citation precision and recall.

Non-goals:

- No change to retrieval, chunking, or the agent prompt.
- No new hosted calls in this round.
- No copy or headline change in this round. Copy changes wait for the owner's reading of the result.
- No new end-to-end sealed pass unless the owner approves a new cap (see Phase 2 in the proposal).

## Constraints

- Repository conventions and gates: `AGENTS.md`, `docs/engineering/repo-conventions.md`, `docs/engineering/code-quality-guidelines.md`. Headline-number and story-language gates apply to any copy.
- Cost: $0 hosted. Any Phase 2 hosted run needs a new cap approved by the owner.
- Downloads: the verifier checkpoint is a file download. Per the owner's rule, it needs explicit approval naming the model, source, and size before Kimi fetches it.
- Dependencies: no new Python dependency without owner approval. `sentence-transformers` already pulls in `transformers` and `torch`, so loading a T5 checkpoint should need no new package. This must be confirmed in the handoff.
- Privacy: no user data involved; corpus is Wikipedia text already committed.
- Latency: verifier cost is not on the answer path in this round; it is measured offline only.

## Options

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| A. Finalize as is; publish the measured miss rates; close the project | Zero cost, honest, nothing to re-verify | The weakest number stays weak; the project reads as unfinished | If the owner wants to stop now |
| B. Retrieval upgrade (embedding, reranker, hybrid) | Familiar, cheap to run offline | Already tested: +1.5 pts recall@10 vs +5 pt gate; low expected gain | Not recommended |
| C. Contextual retrieval (LLM-written chunk context) | Anthropic reports 35–49% fewer retrieval failures | Per-chunk hosted calls across about 593 articles; retrieval is not the bottleneck | Not now |
| D. Grounding-trained verifier challenger (MiniCheck-style), offline on the 194 claims, pre-registered gate | Targets the weakest number; $0 hosted; CPU; directly comparable to committed judges | Possible contamination of the 194 set; download and license steps; may not beat the hosted judge | Recommended first step |
| E. Stricter LLM judge prompt | Simple | Already tried in R8; traded FA for over-abstention | Rejected by evidence |
| F. ALCE-style citation precision and recall, replayed on committed answers | Field-standard metric; $0 | Only as good as the verifier used | Recommended after D passes |
| G. ARES/PPI tighter intervals on verifier FA | Tighter intervals from the same labels | Adds method complexity for a small gain at n=194 | Optional, later |

## Recommendation

Option D first, then F if D passes. Keep A as the fallback: if no verifier passes the gate, the project closes with the current measured numbers and this record of what was tried.

Rationale: the weakest number is the verifier. D is the only option that targets it, costs nothing in hosted calls, and produces a result that can be measured against the committed judges on the same labels. It is also the cheapest way to answer the owner's question of whether the project can be improved at all before spending more.

What this deliberately does not solve: it does not prove the verifier improves end-to-end answer quality. The false-abstention cost of a stricter verifier is measured only on the committed answers in Phase 2, and an end-to-end result needs a separate approved pass.

## Phase plan

- **Phase 1 (this design, $0):** challenger bake-off on the 194-claim set, with a fixed dev/test split. Gate below.
- **Phase 2a (only if Phase 1 passes, $0):** replay the challenger on the committed sealed claims (`citation_records_heldout.json`, `sealed_v2/question_traces_heldout.json`). Report how many claims it would drop, how many it keeps, and the citation precision and recall (ALCE-style). No accuracy claim here, because those claims are unlabeled.
- **Phase 2b (owner decision, needs a new cap):** an end-to-end pass on the 62 unused sealed-v2 questions with the challenger in the verify loop. Estimated hosted cost about $2.2 at the committed rate, so the combined pass total would be about $3.6. This needs a new cap from the owner. It is not part of this design.

## Acceptance criteria

- [ ] Challenger verifier candidates are named with license and checkpoint source, and the owner approves the download before it happens.
- [ ] Dev/test split of the 194 claims is fixed by seed and committed before any scoring.
- [ ] Threshold is chosen on dev only.
- [ ] Test-set results are reported with Wilson 95% intervals for false acceptance over unsupported claims (strict) and false rejection over supported claims.
- [ ] Baseline numbers come from the committed predictions file, not the committed aggregate.
- [ ] Gate is applied as written in the handoff; no gate change after results.
- [ ] No hosted calls. No copy or headline changes.
- [ ] Gates run and reported: pytest, ruff, mypy on new code, `check_headline_numbers.py`, `check_docs.py`.

## Rollback and failure behavior

- Failure modes: download fails or license blocks use; checkpoint loads but scores are unstable on CPU; challenger fails the gate; split leaks into threshold selection.
- Observability: every score is written to a committed predictions file so the result can be re-derived.
- Rollback path: nothing in production changes in this round. Rollback is deleting the new report folder. The verify loop in the app is not touched.

## Open questions

- Owner: approve the verifier download (named checkpoint, source, approximate size) before Kimi fetches it. Candidate: MiniCheck-FT5 (770M). Second candidate, if license or load fails: an NLI cross-encoder, named in the handoff after license check.
- Owner: is the 194-claim set acceptable as the dev/test source given that earlier judges were tuned on it, or should the owner label a fresh claim set first?
- Owner: Phase 2b cap, if Phase 1 passes.
