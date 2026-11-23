# Implementation handoff: Judge Calibration V2 Revision 5 + SOTA Retrieval & Agent Loop Readiness (project 01)

Date: 2026-11-23
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution (Phases A, B, C, and D below; Phase E end-to-end hosted run remains gated on owner review of the 30-claim judge sample)
Branch: `phase0-infra-2026-11-22`
Source design:
- `collaboration/designs/20261122-rag-execution-plan/03-implementation-handoff.md` (Revision 5)
- `collaboration/designs/20261123-rag-sota-retrieval-and-pipeline/01-design-brief.md`
- `collaboration/designs/20261123-rag-sota-retrieval-and-pipeline/02-architecture-proposal.md`

## Objective

1. **Phase A (Judge Calibration V2 — Revision 5):** Fix `build_judge_calibration_v3.py` so it reuses cached `attempt1` drafts, checks 8-grams against *other* claims (`claim != item["claim"]`), checks changed terms with word boundaries and digit support, and varies retry prompts/temperature/seeds. Run it locally, then run `label_judge_calibration_v2.py` (`kimi-for-coding`, hard cap $3.00) and generate `reports/judge_calibration_v2/owner_sample.json` (30 items, seed 44, with `chunk_text`).
2. **Phase B (SOTA Retrieval Ladder — 100% Local, $0 Hosted Spend):** Extend `measure_retrieval.py` with `heldout_55` split support, multi-hop coverage metrics (`all_articles_at_5`, `article_coverage_at_5`, `gold_chunk_coverage_at_5`), `fusion_rrf` (`Bm25Index` + dense RRF top-50 before cross-encoder reranking), and `max_per_article` diversity selection. Evaluate `R0`, `S1` (`structure_200`), `S2` (`structure_hybrid_rrf`), and `S3` (`structure_hybrid_diverse`) across `dev_v1`, `dev_40`, `dev_65`, and `heldout_55`. Run **only the single winning arm once** on `final_v3`.
3. **Phase C (Production Retrieval Promotion & Agent Loop Bounds):** If the winning arm improves `final_v3` retrieval without slice regression, promote it into `src/rag_agent/index.py`, `src/rag_agent/config.py`, and `params.yaml` (with unit tests in `tests/`), and port the bounded agent loop settings (`agent_tool_calls_limit = 16`, `agent_request_limit = 12`, `agent_input_tokens_limit = 200_000`, `search_documents` `top_k` clamped to `1..10`) from `agent-loop-bounds-2026-11-20` into `src/rag_agent/config.py` and `src/rag_agent/agent.py`.
4. **Phase D (Verification & Close-out Report):** Run all project 01 gates (`ruff`, `mypy`, `pytest --cov`) and repo gates (`check_docs.py`), and write `collaboration/reviews/20261123-rag-sota-retrieval-and-pipeline/00-closeout.md`. Do not commit or touch Project 02; Claude will review, validate, and commit.

## Affected surfaces

- `projects/01-rag-agent/scripts/build_judge_calibration_v3.py`
- `projects/01-rag-agent/scripts/label_judge_calibration_v2.py`
- `projects/01-rag-agent/scripts/measure_retrieval.py`
- `projects/01-rag-agent/configs/sweeps/s1_structure_200.yaml` (new)
- `projects/01-rag-agent/configs/sweeps/s2_structure_hybrid_rrf.yaml` (new)
- `projects/01-rag-agent/configs/sweeps/s3_structure_hybrid_diverse.yaml` (new)
- `projects/01-rag-agent/src/rag_agent/config.py`
- `projects/01-rag-agent/src/rag_agent/index.py`
- `projects/01-rag-agent/src/rag_agent/agent.py`
- `projects/01-rag-agent/params.yaml`
- `projects/01-rag-agent/tests/test_index.py` and `projects/01-rag-agent/tests/test_agent.py`
- `projects/01-rag-agent/data/judge_v2_claims.json` and `data/judge_v2_claims.sha256.json`
- `projects/01-rag-agent/reports/judge_calibration_v2/`
- `projects/01-rag-agent/reports/retrieval_sweeps/` and `projects/01-rag-agent/reports/experiment_log.json`
- `collaboration/reviews/20261123-rag-sota-retrieval-and-pipeline/00-closeout.md` (new)

## Ordered implementation steps

### Phase A: Judge Calibration V2 (Revision 5)

1. If a previous `build_judge_calibration_v3.py` process is still running, stop it.
2. Update `projects/01-rag-agent/scripts/build_judge_calibration_v3.py` with the 5 Revision 5 fixes:
   - **Cache hit on matching `prompt_sha256`:** In `generate(prompt, slot, attempt, temperature=0.0, seed=SEED)`, compute `prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()`. If `(DRAFTS / f"{slot}_attempt{attempt}.json")` exists and its JSON `"prompt_sha256" == prompt_sha` and `"response"` is non-empty, record `"localhost"` in `HOSTS` and return `"response"` without calling Ollama.
   - **Exclude self 8-grams by claim text:** For item `i` (`src_claim = item["claim"]`), compute `src_grams = token8(src_claim)` and `other_sup_grams = set().union(*(token8(it["claim"]) for it in supported_items if it["claim"] != src_claim))`. Check collision via `(token8(negative) - src_grams) & (other_sup_grams | accepted_neg_grams)`. When accepted, add `(token8(negative) - src_grams)` to `accepted_neg_grams`.
   - **Word-boundary and digit-aware `changed_term_ok`:**
     - Check presence in `chunk_text` using word boundaries when `term` starts and ends with word characters: `re.search(rf"\b{re.escape(term.lower())}\b", chunk_text.lower())` (fallback to substring otherwise).
     - Allow short numeric terms containing any digit: fail length check only when `len(term) < 4 and not re.search(r"\d", term)`.
   - **Retry feedback and temperature/seed diversity (`attempt > 1`):** Pass `last_reason: str | None` into `draft_negative_once`. When `attempt > 1` and `last_reason` is set, append `\n\nNote: previous attempt failed validation ({last_reason}). Change a DIFFERENT single detail using a word or number that does NOT appear anywhere in the passage.` to the prompt, and pass `temperature=round(0.25 * (attempt - 1), 2)` and `seed=SEED + attempt` to `generate`.
3. Run `HF_HUB_OFFLINE=1 uv run python scripts/build_judge_calibration_v3.py` from `projects/01-rag-agent`. Confirm at least 70 unsupported negatives are accepted (target 75, <= 5 dropped).
4. Run `uv run python scripts/label_judge_calibration_v2.py` (`kimi-for-coding`, hard cap $3.00). Confirm `reports/judge_calibration_v2/owner_sample.json` (30 items, seed 44, with `index`, `claim`, `chunk_id`, `chunk_text`, unlabelled) is written and report total spend and call count.

### Phase B: SOTA Retrieval Ladder (`S1`, `S2`, `S3`)

1. Extend `SweepConfig` and `measure_retrieval.py`:
   - Add fields to `SweepConfig`:
     - `fusion_rrf: bool = False`
     - `rrf_pool_size: int = 50`
     - `max_per_article: int | None = None`
   - Add `"heldout_55"` to `--split` choices (loads `data/golden_heldout.json`, resolving `relevant_titles` to `gold_article_ids`).
   - Add multi-hop coverage metrics to `measure()` output (both top-level and inside each `slices[category]`):
     - `all_articles_at_5`: fraction of answerable questions where `item.gold_article_ids <= {retriever.get_chunk(cid).article_id for cid in ranked[:5] if retriever.get_chunk(cid)}`.
     - `article_coverage_at_5`: mean of `len(retrieved_articles_top5 & item.gold_article_ids) / max(1, len(item.gold_article_ids))`.
     - `gold_chunk_coverage_at_5`: when `item.gold_chunk_ids` is non-empty, mean of `len(set(ranked[:5]) & item.gold_chunk_ids) / len(item.gold_chunk_ids)`, else `None`.
   - When `cfg.fusion_rrf` is `True` or `cfg.max_per_article` is set, use `Retriever`'s extended search (see Phase C item 1 below).
2. Create the 3 sweep config files under `projects/01-rag-agent/configs/sweeps/`:
   - `s1_structure_200.yaml`: `name: s1_structure_200`, `chunk_mode: structure`, `chunk_size: 200`, `chunk_overlap: 40`.
   - `s2_structure_hybrid_rrf.yaml`: `name: s2_structure_hybrid_rrf`, `chunk_mode: structure`, `chunk_size: 200`, `chunk_overlap: 40`, `fusion_rrf: true`, `rrf_pool_size: 50`, `rerank_multiplier: 6`.
   - `s3_structure_hybrid_diverse.yaml`: `name: s3_structure_hybrid_diverse`, `chunk_mode: structure`, `chunk_size: 200`, `chunk_overlap: 40`, `fusion_rrf: true`, `rrf_pool_size: 50`, `rerank_multiplier: 6`, `max_per_article: 2`.
3. Run `baseline`, `s1_structure_200`, `s2_structure_hybrid_rrf`, and `s3_structure_hybrid_diverse` across `dev_v1`, `dev_40`, `dev_65`, and `heldout_55` with `HF_HUB_OFFLINE=1`.
4. Select the single winning arm among `{s1_structure_200, s2_structure_hybrid_rrf, s3_structure_hybrid_diverse}` by `(all_articles_at_5, recall_at_5, mrr_at_5)` on `dev_65` and `heldout_55` (tie-breaking toward simpler arm `S1 < S2 < S3`).
5. Run **only that single winning arm once** on `final_v3`:
   `HF_HUB_OFFLINE=1 uv run python scripts/measure_retrieval.py --split final_v3 --config configs/sweeps/<winner>.yaml`
   Log the result in `reports/experiment_log.json`.

### Phase C: Production Retrieval Promotion & Agent Loop Bounds

1. In `src/rag_agent/index.py` and `src/rag_agent/config.py`:
   - Add optional fields to `RAGConfig` (and `RetrievalBest`):
     - `chunk_mode: Literal["size", "structure"] = "structure"` (if an `S*` arm beat `R0` on `final_v3`, else keep `"size"` as default while supporting `"structure"`).
     - `fusion_rrf: bool = ...` (matching the `final_v3` winner).
     - `rrf_pool_size: int = Field(default=50, ge=5)`
     - `max_per_article: int | None = Field(default=..., ge=1)` (matching the `final_v3` winner).
   - Update `chunk_articles(articles, size, overlap, chunk_mode="size")` in `src/rag_agent/index.py` so when `chunk_mode == "structure"` it calls `chunk_by_structure(article.text, article.article_id, article.title, size=size, overlap=overlap)`.
   - In `Retriever`:
     - Lazily build a `Bm25Index(self.chunks)` from `rag_agent.lexical` when `self.config.fusion_rrf` (or `fusion_rrf=True`) is enabled.
     - In `Retriever.search(query, top_k=None)`:
       1. Compute `n_candidates = min(len(self.chunks), k * self.config.rerank_multiplier)`.
       2. If `fusion_rrf` is enabled: fetch top `pool = min(len(self.chunks), max(n_candidates, self.config.rrf_pool_size))` from FAISS and top `pool` from `Bm25Index.ranking(query)`, fuse via `reciprocal_rank_fusion([dense_ids, bm25_ids], k=60)`, and take the top `n_candidates` `ChunkRecord`s.
       3. Rerank the `n_candidates` with `self.rerank_fn` if present.
       4. If `max_per_article` is set (and `> 0`): iterate through reranked `candidates`, accepting a chunk if `article_counts[chunk.article_id] < max_per_article` and placing overflow chunks in a `deferred` list; if fewer than `k` chunks were selected, backfill from `deferred` in score order up to `k`.
2. In `src/rag_agent/config.py` and `src/rag_agent/agent.py` (porting the verified loop bounds from `agent-loop-bounds-2026-11-20`):
   - Add to `RAGConfig`:
     - `agent_request_limit: int = Field(default=12, ge=1)`
     - `agent_tool_calls_limit: int = Field(default=16, ge=1)`
     - `agent_input_tokens_limit: int = Field(default=200_000, ge=1_000)`
   - In `agent.py`, clamp `search_documents` `top_k` to `max(1, min(top_k, 10))` and expose a helper `agent_usage_limits(config: RAGConfig) -> UsageLimits` combining `budget_limits()` with `request_limit=config.agent_request_limit`, `tool_calls_limit=config.agent_tool_calls_limit`, `input_tokens_limit=config.agent_input_tokens_limit`, wired into `evaluate.py`'s agent calls.
3. Add unit tests in `tests/test_index.py` (covering `chunk_mode="structure"`, `fusion_rrf=True`, and `max_per_article=2` with backfill) and `tests/test_agent.py` (covering `top_k` clamping and `agent_usage_limits`).
4. If the winning `S*` arm improved `final_v3`, update `params.yaml` `retrieval_best` and rebuild `data/index/chunks_200` locally so the production index matches the promoted winner.

### Phase D: Gates & Close-out Report

Run all gates and record their exact outputs in `collaboration/reviews/20261123-rag-sota-retrieval-and-pipeline/00-closeout.md`:

```bash
cd /Users/alejandro/work/portfolio/projects/01-rag-agent
uv run pytest --cov
uv run ruff check . && uv run ruff format --check . && uv run mypy .
cd /Users/alejandro/work/portfolio
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Phase A complete: `data/judge_v2_claims.json` (75 supported + >= 70 one-detail same-subject negatives), `data/judge_v2_claims.sha256.json`, Kimi labels under $3.00 cap, and `reports/judge_calibration_v2/owner_sample.json` (30 items with `chunk_text`).
- [ ] Phase B complete: `R0`, `S1`, `S2`, `S3` measured across `dev_v1`, `dev_40`, `dev_65`, and `heldout_55` with `all_articles_at_5`, `recall_at_5`, `mrr_at_5`; single winning arm measured **once** on `final_v3` and logged in `reports/experiment_log.json`.
- [ ] Phase C complete: winning retrieval config and bounded agent loop (`agent_tool_calls_limit = 16`, `top_k` clamp) integrated in `src/rag_agent/` with passing unit tests.
- [ ] Phase D complete: `uv run pytest --cov` (>= 78.45% floor), `ruff`, `mypy`, and `check_docs.py` all pass; `00-closeout.md` written.
- [ ] Zero hosted calls outside Phase A's `kimi-for-coding` labelling; no git commits or pushes (Claude will review, validate, and commit); Project 02 untouched.

## Stop conditions

- Phase A spend reaching $3.00.
- Any non-localhost request in Phase B or Phase C.
- More than one candidate run on `final_v3` in Phase B.
- Coverage dropping below 78.45%.
