# R4 retrieval baseline — dense vs BM25 on the sealed set

Generated: 2026-11-19T15:59:23.395309+00:00 · n = 42 answerable sealed questions (of 55 total) · retrieval-only, rerank off.

| retriever | recall@5 | Wilson 95% | recall@10 | MRR@5 |
|---|---|---|---|---|
| dense (MiniLM, committed FAISS) | 0.9762 | [0.8768, 0.9958] | 1.0000 | 0.9008 |
| BM25 (k1=1.2, b=0.75) | 0.9524 | [0.8421, 0.9868] | 0.9762 | 0.8790 |

Point estimates recomputed and verified against the committed `reports/sealed_retrieval.json` arms (dense 0.9762, BM25 0.9524). New files only; no committed record touched.
