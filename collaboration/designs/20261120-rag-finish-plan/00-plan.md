# Plan: finish project 01 with measured results

Date: 2026-11-20
Designer: Claude Code
Status: draft for owner decision. Nothing here is approved for execution.
Inputs: the 2026 RAG survey the owner shared; `projects/01-rag-agent/DESIGN.md` §6 (changelog); `reports/retrieval_tournament/results.json`; `collaboration/reviews/20261120-verifier-reconciliation-report/00-report.md`; `collaboration/reviews/20261120-verifier-cascade-dev-report/00-report.md`.

## 1. What the survey recommends, against what this project already measured

| Survey recommendation | Status in project 01 | Evidence |
|---|---|---|
| Hybrid retrieval (BM25 + dense, RRF) | Tested, not promoted | Tournament arm with BM25/RRF; +1.5 pts recall@10 vs +5 pt gate |
| Cross-encoder reranking | Already in the pipeline | `ms-marco-MiniLM-L-6-v2` rerank in `params.yaml` |
| Stronger reranker (Qwen3-Reranker) | Tested, not promoted | Same tournament |
| Stronger embeddings (Qwen3-Embedding) | Tested, not promoted | Same tournament |
| Structure-aware / parent-child chunking | Tested in tournament (structure-aware); parent expansion not tested | DESIGN §6 1.1.0 |
| Query rewriting, multi-query, HyDE | Not tested | — |
| Self-correction / corrective RAG | Partly: verify loop with repair and abstention | DESIGN §6 1.0.0 |
| GraphRAG | Not tested; retrieval is not the bottleneck | 9 of 11 sealed failures retrieved the gold article at rank 1 |
| Multi-hop decomposition | Not tested; little headroom (recall@10 = 1.0 on multi-hop) | `reports/retrieval_tournament/results.json` slice audit |
| Evidence verification, claim-level | Tested extensively: four verifier approaches, all hit the FA/FR trade-off | Phase 1 challenger; cascade DEV (0 of 4,095 bands qualify) |
| Evaluate each stage separately, human labels | Partly: rubric judge and deterministic checks; no human-audited sample yet | DESIGN §6; survey §6 |

Conclusion: the survey's highest-impact items are already measured and closed here. The open problem is the one the survey also flags: LLM-judge-only evaluation, with a judge gap that does not reconcile.

## 2. Remaining work, in order

### Phase 0 — resolve the judge reconciliation (blocking; $0; local only)

- Re-run `calibrate_judge.py` unchanged, twice, on the same Ollama digest. This separates code-path difference from runtime drift.
- Outcome decides the copy: if 0.4433 reproduces, keep it with its script hash; if not, the README and docs lines that cite 0.4433 are replaced with the reproduced figure or removed.
- Owner approval needed for any copy edit.

### Phase 1 — human-audited sample (owner labels; $0 hosted)

- The survey's own point: do not optimize on LLM judges alone.
- Owner hand-labels 30–40 answers from the committed sealed traces (`reports/sealed_v2/question_traces_heldout.json`), each marked supported or unsupported at the claim level.
- Score the same answers with the rubric judge; report agreement and a prediction-powered estimate of the unsupported rate with an interval (ARES-style PPI).
- Outcome: if the rubric judge disagrees with the owner on more than about 25% of labeled answers, the 26% headline is reported as unreliable, and copy changes to say so.

### Phase 2 — one confirmatory generation pass (owner approval and cap; ~$2)

Only if Phase 0 and Phase 1 leave the question open.

- Fresh set: the 62 sealed_v2 questions outside `golden_sealed_v2_58.json`, defined by exclusion and hashed before the run.
- One candidate change, chosen to target the measured failure (unsupported claims with no abstention cost): answer from verbatim quoted spans only, and fall back to extractive quotes rather than refusal when verification drops claims.
- Pre-registered success, fixed now: unsupported-answer rate among answerable questions ≤ 0.15, false abstention ≤ 0.15, paired McNemar against the current verify loop on the same drafts.
- Cap: $2.00 hosted on `kimi-for-coding`, owner-approved. Stop at $1.80 cumulative.
- If it fails, the production configuration stays and the failure is reported.

### Phase 3 — finish

- Update copy only to numbers that have passed Phases 0–2, each traced to a committed artifact.
- Close the project with a results table: what was tried, what was measured, what was rejected and why.
- Retire the claims that do not reproduce.

## 3. What this plan deliberately does not do

- No new retrieval experiments (tournament already closed them).
- No GraphRAG, no multi-hop decomposition, no multimodal work: retrieval is not the bottleneck, and the survey's own cost notes say GraphRAG needs substantial indexing.
- No new verifier model. The FA/FR trade-off was measured across four approaches.
- No change to the production configuration unless Phase 2 passes and the owner approves.

## 4. Decisions the owner needs to make

1. Approve Phase 0 (local re-run of `calibrate_judge.py`, two repeats).
2. Approve Phase 1 and provide 30–40 hand labels (or say the audit is not wanted; then the headline stays as "rubric judge, unaudited").
3. Approve or hold Phase 2 ($2.00 cap). It runs only after Phases 0 and 1.
4. Approve or reject the false-rejection cap of 0.10 for any future verifier. The survey's implied bar is looser; the project's gate stays at 0.10.
