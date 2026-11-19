# 01 RAG agent (flagship): investigation

Date: 2026-11-19 (searches run on the session date 2026-11-18). Reviewer: Sonnet. Labels: SB = source-backed, SEC = secondary, GAP = no source found. Source IDs map to `99-sources.md`.

## Current state (committed)
- Headline: frozen 30-question stress re-run 0.733 correct, CI [0.567, 0.867]; unsupported 5 of 30 (was 11, "not a demonstrated gain"); independent set B 0.633, 9/30 unsupported over the <=6/30 gate; not unattended-ready. Source: `projects/01-rag-agent/story.yaml` (short_version). Metrics: `projects/01-rag-agent/reports/metrics.json`.
- Judge calibration committed and NOT accepted: local judge qwen2.5:3b false-acceptance 0.4433 (UCB95 0.5136), kappa 0.5464, 194 claims / 80 answers, `ACCEPTS: false` (`reports/judge_calibration/results.json`); qwen3:4b false-acceptance 0.4536, kappa 0.5361, `ACCEPTS: false` (`reports/judge_calibration_hosted/results.json`).
- Retrieval tournament on 65 tuning questions: R1, R2, R5a, R5b each +0.0154 recall@10 and none clears the promotion gate (`reports/retrieval_tournament/results.json`). Chunk sizes tie at recall@5 0.831 (story roadmap).
- Roadmap "next": write a fresh sealed set first (set B failed two gates).

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | The claim check scores citation relevance, not warrant strength. ForceBench: 198 contrastive pairs, five axes (relation, modality, scope, temporal validity, numeric specificity); generic support prompting MVR 47.2%, explicit warrant prompting 24.5%, aggregated over four judges. The prompts name the five axes, so part of the gain may be task framing (aggregator note). | SB for the paper's abstract figures; SEC for the framing caveat | S01, aggregator pointer only: benchmarklist.com |
| G2 | The only calibrated judges are 3-4B local models with false-acceptance about 0.44-0.45. Small purpose-built checkers exist (MiniCheck, 770M, claimed GPT-4-level on LLM-AggreFact at far lower cost). Not run here. | SEC | S52 |
| G3 | Judge agreement reporting: guidance says report kappa against a human-human baseline, bootstrap CIs, and re-calibrate when judge, prompt or task changes. The repo already reports kappa and UCB; it has no human-human baseline. | SEC | S09, S10 |
| G4 | Sealed-set reuse: adaptive reuse of a held-out set can overfit; guarantees degrade under adaptivity. No source found for a minimum sealed-set size for CI width at n=30-55. | SEC (reuse), GAP (sizing) | S53, S54 |
| G5 | Retrieval: recall@5 ties across chunk sizes and R1-R5 do not clear the gate. Hybrid BM25+dense+reranker is the common default in practitioner write-ups, but I found no primary benchmark table; one write-up reports hybrid below dense-only. | SEC (blogs), GAP (primary) | S56 |
| G6 | RAGAS faithfulness is statement-level support fraction, validated on WikiEval; vendor docs treat it as directional. Our three-judge stack is consistent with this. | SEC | S08 |

## Candidate improvements
**A. Offline claim-level checker, calibrated on the existing 194-claim label set** (recommended first).
- Method: run a small local NLI-style grounding model (MiniCheck family) over the committed claim records (`reports/citation_records_heldout.json`, judge-calibration claims) and score false-acceptance, false-rejection and kappa with bootstrap CIs, using the same acceptance rule that produced `ACCEPTS: false`. Report as a new file, for example `reports/judge_calibration_nli/results.json`; do not edit the existing results.
- Reference: https://arxiv.org/html/2404.10774v2 (S52).
- Cost: compute only (CPU or small GPU; model download needs owner OK). Estimate 1-2 engineering days.
- Stop condition: false-acceptance UCB95 not below the committed local-judge value (0.5136) after one prompt/threshold sweep fixed on a dev split, or the model licence blocks use.

**B. Warrant-strength rubric and a small contrastive set built from our own failures.**
- Method: write 40-60 contrastive pairs from the 9-of-11 grounding failures (claim vs overstated claim on a fixed cited passage), label by hand, and measure MVR for the current rubric versus a warrant-strength rubric. Hosted judge calls only after owner approval; a local run is possible first.
- Reference: https://arxiv.org/abs/2605.28044 (S01).
- Cost: labelling effort (owner or designer, about 1 day) plus hosted calls under an owner-approved cap (amount: to be set by owner; no price assumed here).
- Stop condition: pairs show MVR no better than the current rubric on 40 pairs, or the owner declines the hosted cap.

**C. Fresh sealed set C with a pre-registered size and one-shot use.**
- Method: draft 60+ questions never shown to any tuning loop, record gate thresholds before the run, evaluate once, report binomial/Wilson CIs. Add a public/private gap check as the overfitting signal.
- Reference: https://arxiv.org/pdf/2107.07002 (S53); https://papers.nips.cc/paper/9117-a-meta-analysis-of-overfitting-in-machine-learning (S54). Sizing guidance: GAP.
- Cost: question writing (about 1-2 days); the evaluation run itself needs hosted generation under a cap.
- Stop condition: any question used for tuning before the run invalidates the set; stop and rewrite.

**D. Hybrid retrieval arm (BM25 + dense with reciprocal-rank fusion, optional cross-encoder rerank).**
- Method: add as arm R6 to the existing tournament; same promotion gate. Low expected value because recall already ties across settings and 9 of 11 failures are grounding, not retrieval.
- Reference: S56 (practitioner blog, SEC); BEIR primary text not read (GAP).
- Cost: compute only, about 1 day.
- Stop condition: delta recall@10 under +0.02 or gate not cleared, as for R1-R5.

## Ranked recommendation
1. A (offline checker on the committed label set): high value, compute only, verifiable offline.
2. B (warrant-strength contrastive set): high value for the flagship claim; needs a hosted cap.
3. C (fresh sealed set): required before any new quality claim, per the roadmap; labour-heavy.
4. D (hybrid arm): low value now.

No number change is proposed. A and B would add new files and new numbers (overstated-claim rate, checker false-acceptance).

## Queries used (all standard mode, date 2026-11-18)
- "ForceBench warrant strength RAG claim support judge monotonicity"
- "RAGAS faithfulness metric paper automated evaluation of retrieval augmented generation"
- "LLM-as-a-judge calibration human agreement Cohen's kappa best practices survey"
- "MiniCheck efficient fact-checking grounding documents small model LLM-AggreFact benchmark"
- "benchmark contamination held-out test set reuse adaptive overfitting sealed evaluation set size confidence interval small test sets"
- "retrieval-augmented generation hybrid BM25 dense reranker benchmark BEIR MTEB retrieval evaluation 2026 embedding models"
- Fetched: arxiv.org/abs/2605.28044.
