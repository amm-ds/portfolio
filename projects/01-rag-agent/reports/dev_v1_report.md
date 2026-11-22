# dev_v1 leakage report

Source: tuning-65 (`src/rag_agent/eval_questions.json`), sha256 `fe6b2529e07682f5ee42c72898bd6069cc697154bda43325c8985774b5d2eabd`.
Selected ids (seed 42): [1, 2, 3, 4, 6, 9, 12, 13, 14, 15, 16, 23, 28, 29, 33, 34, 35, 47, 55, 61]

## Leakage (zero exact duplicates required)

- sealed_120: 0 exact duplicates — PASS
- final_v3: 0 exact duplicates — PASS
- heldout_55: 0 exact duplicates — PASS

## Decision-metrics note

20 questions is too few for F1 decisions: retrieval recall@5 and MRR are the decision metrics until dev reaches 65. dev_v1 is drawn from the tuning set, which chose the retrieval config (params.yaml retrieval_best); dev results are not clean for those choices - only final_v3 gives an unbiased number.
