# Project 01 (RAG Agent) — Iteration & Plan Tracker

Last updated: 2026-11-23
Branch: `phase0-infra-2026-11-22`
Architect / Reviewer / Committer: Claude Code
Executor: Kimi Code

---

## 1. North-Star Target & Operating Rules

- **Primary Target:** Per-question F1 of **0.85 to 0.90** on `golden_final_v3.json` (120 questions: 68 single-hop, 24 multi-hop, 28 unanswerable) with **zero errors** (0 unsupported claims, 0 false abstentions, 0 wrong abstentions, 0 budget terminations).
- **Judge Requirement:** Validated on `data/judge_v2_claims.json` (147 claims: 75 supported + 72 one-detail same-subject negatives) with **$\ge 85\%$ agreement** against the 30-claim blind sample (`owner_sample.json`). **Achieved: 30/30 = 100.0% (Wilson 95% [0.8865, 1.0000])** (`owner_sample_validated.json`).
- **Split Hygiene:**
  - Tune and iterate locally on `dev_v1` (20) $\to$ `dev_40` (40) $\to$ `dev_65` (65 tuning questions) + `heldout_55` (55 held-out questions).
  - Run `final_v3` (120) **at most once per promoted winner**.

---

## 2. Iteration Ledger

| Iteration | Handoff / Design | Scope & Changes | Key Measured Metrics | Status | Commit |
|---|---|---|---|---|---|
| **Phase 0** | `20261122-rag-phase0-infra` | Build `golden_final_v3.json` (120 frozen questions), `dev_v1.sha256.json` (20 dev questions), and `src/rag_agent/runner.py` (per-question checkpoints, sha256 guard, host capture) | 120 questions frozen (`68` single-hop, `24` multi-hop, `28` abstain); 0 exact leakage across splits | **DONE** | `791cf78`, `4f4660c` |
| **Iter 1 (Steps 0, 2–6)** | `20261122-rag-execution-plan` | Pinned `R0` retrieval baseline (`size` 200/40, MiniLM, ms-marco reranker) + 5 single-axis sweeps on `dev_v1` (`chunk_400`, `chunk_800`, `bge-small`, `qwen3-embed`, `Qwen3-Reranker-0.6B`) + `R0` baseline on `final_v3` | `dev_v1` `R0`: Recall@5 **1.0000**, MRR@5 **0.9688**.<br>`final_v3` `R0`: Recall@5 **0.9239** (85/92), MRR@5 **0.8793** (`single_hop` **0.9706**, `multi_hop` **0.7917**, abstain false-evidence **0/28**). | **DONE** | `1663dd3`, `7e3246a` |
| **Iter 2 (Phase A)** | `20261122-rag-execution-plan` (Rev 5) & `20261123-rag-sota-retrieval-and-pipeline` | Patch `build_judge_calibration_v3.py` (cache-hit `attempt1`, exclude self 8-grams by claim text, word-boundary + digit check, retry feedback + temp/seed variation) $\to$ `label_judge_calibration_v2.py` (`kimi-for-coding`, `$0.0948` spend, `$0.1994` cumulative) $\to$ audit 30-item `owner_sample.json`. | **147 claims** (`75` supported + `72` same-subject 1-detail negatives, 3 dropped; overlap 5–17 shared content words).<br>**30-item blind sample audit:** **30/30 = 100.0%** (Wilson 95% **[0.8865, 1.0000]** $\ge 85\%$ gate PASS). | **DONE & VALIDATED** | Committing this turn |
| **Iter 2 (Phases B–D)** | `20261123-rag-sota-retrieval-and-pipeline` | SOTA Retrieval Ladder ($0 local):<br>- `S1`: `structure_200` (title-prefixed chunks)<br>- `S2`: `structure_hybrid_rrf` (`S1` + Dense-50 & BM25-50 RRF $\to$ Cross-Encoder top-30)<br>- `S3`: `structure_hybrid_diverse` (`S2` + per-article cap `max_per_article=2` in top-5)<br>Winner `S3` run once on `final_v3` and promoted into `src/rag_agent/` + `params.yaml` + `agent_usage_limits` (`12/16/200_000` + `top_k` clamp `1..10`). | `dev_65`: `all_articles@5` **0.745 $\to$ 0.891**, `recall@5` **0.964 $\to$ 0.982**, `MRR@5` **0.945 $\to$ 0.973**.<br>`heldout_55`: `all_articles@5` **0.952 $\to$ 0.976**, `recall@5` **0.976 $\to$ 1.000**, `MRR@5` **0.940 $\to$ 0.982**.<br>**`final_v3` (`S3` vs `R0`):**<br>- `recall@5`: **0.9239 $\to$ 0.9457** (+2.2 pp)<br>- `MRR@5`: **0.8793 $\to$ 0.8877** (+0.8 pp)<br>- `single_hop`: **0.9706 $\to$ 0.9853** (67/68)<br>- `multi_hop`: **0.7917 $\to$ 0.8333** (+4.2 pp)<br>- `all_articles@5`: **0.8804**, `article recall@10`: **92/92 = 1.0000** (`validate_heldout_set` 0 problems)<br>- `pytest --cov`: **181 passed**, `81.14%` coverage (`> 78.45%` floor). | **DONE & VALIDATED** | Committing this turn |
| **Iter 3 (Phase E — Steps 1–2)** | `20261123-rag-phase-e-e2e-and-judge-fix` | Fix 3 E2E bugs (`evaluate.py` full-chunk `_judge_context`, `verify.py` punctuation-safe `span_token_sets`, `agent.py` Rule 5 search cap) + run 20-question `dev_v1` E2E gate (`$0.335` spend, `$0.5344` cumulative of `$3.00`). | **`dev_v1` (20 questions):**<br>- **`F1 = 0.9032`** (`>= 0.85` PASS), `precision = 0.9333`, `recall = 0.8750`<br>- **`unsupported_claim = 0`** (down from 25–30%!), `format_failure = 0`<br>- `12/12` `single_hop` correct (`100%`)<br>- Stopped at gate due to `1` `budget-terminated` unanswerable row (`"What is the capital of Australia?"`) and `2` `multi_hop` `empty-answer` rows (both `faithfulness = 0.9`, `claim_states = None`). | **DONE (GATE CAUGHT 3 ROWS)** | Committing this turn |
| **Iter 3 (Phase E — Rev 1 & Step 3)** | `20261123-rag-phase-e-e2e-and-judge-fix` (Rev 1) | 1. Deterministic in-tool soft budget ceiling (`requests >= 9` or `tool_calls >= 12` returns `TOOL BUDGET REACHED` notice so model emits `AnalysisResult` before `request_limit=12`).<br>2. Multi-hop synthesis Rule 10 + `verify.py:559` only skips verification when `not result.claims or result.confidence < 0.3`.<br>3. `--retry-failed` re-evaluates only the 3 failed `dev_v1` rows (~`$0.05`, reusing 17 passing rows) $\to$ runs checkpointed 120-question `final_v3` pass (`LLM_COST_LIMIT_USD=2.40`, `HF_HUB_OFFLINE=1`). | Target on `dev_v1`: `F1 >= 0.93+`, `budget_terminated == 0`.<br>Target on `final_v3` (120 questions): Per-question F1 **`0.85–0.90+`**, **`0`** budget terminations, near-zero unsupported claims. | **READY FOR KIMI** | Committing this turn |

---

## 3. Workflow Loop (Claude $\leftrightarrow$ Kimi)

1. **Claude** reviews results, architects the next iteration under `collaboration/designs/`, updates `collaboration/ITERATION_TRACKER.md`, validates gates, commits to git, and outputs the **Execution Snippet for Kimi**.
2. **Owner** pastes the snippet into Kimi's terminal.
3. **Kimi** executes the exact handoff steps, runs project gates, writes `collaboration/reviews/<handoff>/00-closeout.md`, and stops without committing.
4. **Claude** verifies the close-out report, runs repository validation gates, commits the verified implementation, and prepares the next iteration.
