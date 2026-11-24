# Design brief: SOTA retrieval upgrade and end-to-end pipeline readiness (project 01)

Date: 2026-11-23
Designer: Claude Code
Owner: session owner (portfolio repo)
Status: approved for local execution (Round 2 retrieval & production integration; hosted end-to-end gated on Step 1 judge validation)

## Problem

Iteration 1 (`20261122-rag-execution-plan`, close-out `collaboration/reviews/20261122-rag-execution-plan/00-closeout.md`) established the pinned baseline (`R0`: `chunk_mode: size`, 200/40, `all-MiniLM-L6-v2`, `ms-marco-MiniLM-L-6-v2`, `top_k: 3`, `measure_k: 5`, `rerank_multiplier: 5`):

- On `dev_v1` (16 answerable questions), `R0` was already at ceiling (`recall@5 = 1.0000`, `MRR@5 = 0.9688`). Because `200`, `400`, and `800` all tied at `1.0000`, the structure-aware chunking arm (`chunk_mode: structure`) was never triggered, and the `+0.10` `dev_v1` promotion gate was mathematically unreachable.
- On the unbiased `final_v3` set (92 answerable, 28 unanswerable), `R0` scored **`recall@5 = 0.9239` (85/92, Wilson 95% [0.8512, 0.9627]), `MRR@5 = 0.8793`**, with **`multi_hop` dropping to `0.7917` (19/24)** while `single_hop` scored `0.9706` (66/68).
- Furthermore, `measure_retrieval.py` currently scores a multi-hop question as a hit if *any one* gold chunk appears in top-5 (`any_hit@5`), masking cases where the second required article is crowded out of the top-5 by multiple chunks from the first article.

## Root causes identified in code (`src/rag_agent/index.py`, `chunking.py`, `lexical.py`)

1. **Unanchored body chunks (`chunk_mode: size`):** `chunk_by_size` omits `article.title` from chunk text. Body chunks `#c001..#c015` frequently use pronouns or domain nouns without repeating the article title, degrading both bi-encoder recall and cross-encoder reranking (`self.rerank_fn(query, [c.text for c in candidates])`). By contrast, `chunk_by_structure` prefixes `f"{title}\n\n{body}"` while keeping `_pack` boundaries and `chunk_id`s (`{article_id}#c{i:03d}`) 100% identical (already achieving `55/55 = 1.0000` on `tuning-65` in `reports/retrieval_tournament/results.json`).
2. **Dense-only candidate generation:** `src/rag_agent/lexical.py` already implements deterministic `Bm25Index` (k1=1.2, b=0.75) and `reciprocal_rank_fusion(k=60)`, but `Retriever.search` in `index.py` only fetches `n_candidates = k * rerank_multiplier` (`25` at `k=5`) from dense FAISS. Exact numbers, dates, technical terms, and secondary multi-hop entities missed by dense top-25 never reach the cross-encoder.
3. **Single-article monopolization in top-k:** On multi-hop questions spanning two articles, a multi-chunk primary article can occupy all 5 top-k slots after reranking, leaving 0 slots for the second hop's article.
4. **Missing loop bounds and checkpoint wiring on `phase0-infra-2026-11-22`:** `runner.py` implements per-question checkpoints (`reports/runs/<run_id>/rows.jsonl`), and `agent-loop-bounds-2026-11-20` proved that `agent_tool_calls_limit = 16` + `search_documents` `top_k` clamping are required to avoid budget terminations, but neither is wired into `RAGConfig` / `evaluate.py` on `phase0-infra-2026-11-22`.

## Goal

1. Finish Step 1 Judge Calibration V2 via Revision 5 (fast-path cached drafts + fixed 8-gram self-collision + word-boundary check + Kimi labelling).
2. Upgrade retrieval via a disciplined 3-arm SOTA ablation ladder (`S1: structure_200`, `S2: structure_hybrid_rrf`, `S3: structure_hybrid_diverse`) evaluated across `dev_v1`, `dev_40`, `dev_65`, and `heldout_55` (all local, $0 spend) with full multi-hop coverage metrics (`all_articles_at_5`, `article_coverage_at_5`, `recall_at_5`, `mrr_at_5`), followed by **one** final verification run of the winning configuration on `final_v3`.
3. Promote the winning retrieval architecture and bounded/checkpointed agent evaluation loop into `src/rag_agent/`, rebuild the committed index `data/index/chunks_200`, pass all project and repo gates, and commit cleanly so the pipeline is ready for the single end-to-end `final_v3` pass once the owner validates the 30-claim judge sample.
