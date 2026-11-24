# Architecture proposal: SOTA hybrid title-anchored retrieval with article diversity and checkpointed agent bounds

Date: 2026-11-23
Designer: Claude Code
Source brief: `collaboration/designs/20261123-rag-sota-retrieval-and-pipeline/01-design-brief.md`

## 1. Retrieval architecture ladder (`S1` → `S2` → `S3`)

All three arms retain `chunk_size: 200`, `chunk_overlap: 40`, `all-MiniLM-L6-v2` (CPU, offline), and `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU, offline), ensuring zero external dependencies, deterministic CPU execution, and 100% `chunk_id` compatibility (`{article_id}#c{i:03d}`) with `golden_final_v3.json` (`chunk_exact` gold mode).

| Arm | Config file | `chunk_mode` | Candidate stage | Cross-encoder rerank | Post-rerank selection | Target bottleneck |
|---|---|---|---|---|---|---|
| `R0` (incumbent) | `configs/sweeps/baseline.yaml` | `size` (no title) | Dense FAISS top 25 (`5 * 5`) | `ms-marco-MiniLM-L-6-v2` over `chunk.text` | Top-`k` raw order | Baseline reference |
| `S1` (`structure_200`) | `configs/sweeps/s1_structure_200.yaml` | `structure` (`f"{title}\n\n{body}"`) | Dense FAISS top 25 (`5 * 5`) | `ms-marco-MiniLM-L-6-v2` over title-prefixed `chunk.text` | Top-`k` raw order | Unanchored body chunks (`#c001..#c015`) |
| `S2` (`structure_hybrid_rrf`) | `configs/sweeps/s2_structure_hybrid_rrf.yaml` | `structure` | Dense top 50 + `Bm25Index` top 50 fused via `reciprocal_rank_fusion(k=60)` → top 30 (`measure_k * 6`) | `ms-marco-MiniLM-L-6-v2` over top 30 RRF candidates | Top-`k` raw order | Exact terms, dates, numbers, and secondary entities missed by dense-only top-25 |
| `S3` (`structure_hybrid_diverse`) | `configs/sweeps/s3_structure_hybrid_diverse.yaml` | `structure` | Same as `S2` (Dense 50 + BM25 50 → RRF top 30) | Same as `S2` | Per-article cap `max_per_article = 2` in top-`k` (with deterministic score-order backfill if needed) | Multi-hop queries where one multi-chunk article monopolizes all 5 top-`k` slots |

### Why this is the smallest complete change

- `chunk_by_structure` already exists in `src/rag_agent/chunking.py` (lines 163–174) and is already unit-tested.
- `Bm25Index` and `reciprocal_rank_fusion` already exist in `src/rag_agent/lexical.py` (lines 134–196) and are already unit-tested.
- Adding optional `chunk_mode: Literal["size", "structure"] = "structure"`, `fusion_rrf: bool = True`, `rrf_pool_size: int = 50`, and `max_per_article: int | None = 2` to `RAGConfig` / `Retriever` wires existing verified building blocks into the live `Retriever.search()` path without adding any third-party package.

## 2. Multi-hop observability in `measure_retrieval.py`

In addition to `recall_at_5` (any gold chunk/article hit in top-5) and `mrr_at_5`:

- `all_articles_at_5`: for each answerable question, `1.0` if every `aid in item.gold_article_ids` appears in `{retriever.get_chunk(cid).article_id for cid in ranked[:5]}`, else `0.0`. (On single-hop questions with 1 gold article, this equals article-level `recall_at_5`; on multi-hop questions with 2 gold articles, it requires **both** legs to be retrieved in top-5.)
- `article_coverage_at_5`: mean of `len(retrieved_article_ids_top5 & item.gold_article_ids) / len(item.gold_article_ids)`.
- `gold_chunk_coverage_at_5`: when `item.gold_chunk_ids` is non-empty (`final_v3`), mean of `len(set(ranked[:5]) & item.gold_chunk_ids) / len(item.gold_chunk_ids)`.

## 3. Promotion protocol (strictly preserving `final_v3` hygiene)

1. Run `R0`, `S1`, `S2`, and `S3` on `dev_v1` (20), `dev_40` (40), `dev_65` (65 tuning questions), and `heldout_55` (`data/golden_heldout.json`, 55 held-out questions). All runs are 100% local (`HF_HUB_OFFLINE=1`, zero network/Ollama calls).
2. Select the single winning arm among `{S1, S2, S3}` lexicographically by `(all_articles_at_5, recall_at_5, mrr_at_5)` on `dev_65` + `heldout_55`, breaking ties in favor of the simpler arm (`S1 < S2 < S3`), subject to zero regression on `single_hop` and `multi_hop` slices and `n_abstain_false_evidence == 0`.
3. Run **only the single winning arm once** on `final_v3` (`--split final_v3`) and log the before/after lift against `R0` (`0.9239` recall@5, `0.7917` multi-hop recall@5, `0.8793` MRR@5) in `reports/experiment_log.json`.
4. If the winning arm improves `final_v3` (`recall_at_5` and/or `all_articles_at_5` and `mrr_at_5` with no slice drop), promote it into `src/rag_agent/index.py`, `src/rag_agent/config.py`, and `params.yaml`, and rebuild `data/index/chunks_200`.

## 4. Agent loop bounds & checkpoint wiring (port from `agent-loop-bounds-2026-11-20` + `runner.py`)

To prepare for the hosted end-to-end evaluation pass (after Step 1 judge validation):

- Port the 4 bounded-loop config fields from `agent-loop-bounds-2026-11-20` (`335785b`, `f2cc771`, `520e3b2`, `6a1e6bf`) into `RAGConfig` and `agent.py`:
  - `agent_request_limit: int = 12`
  - `agent_tool_calls_limit: int = 16`
  - `agent_input_tokens_limit: int = 200_000`
  - Clamp `search_documents(top_k)` to `max(1, min(top_k, 10))`.
- Ensure `evaluate.py` held-out evaluation integrates with `rag_agent.runner.Checkpoint` when `--checkpoint-dir` (or `--run-id`) is active so every completed question flushes immediately to `reports/runs/<run_id>/rows.jsonl`.
