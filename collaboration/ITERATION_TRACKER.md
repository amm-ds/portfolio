# Project 01 (RAG Agent) — Iteration & Plan Tracker

Last updated: 2026-11-23
Branch: `phase0-infra-2026-11-22`
Architect / Reviewer / Committer: Claude Code
Executor: Kimi Code

---

## 1. North-Star Target & Operating Rules

- **Primary Target:** Per-question F1 of **0.85 to 0.90** on `golden_final_v3.json` (120 questions: 68 single-hop, 24 multi-hop, 28 unanswerable) with **zero errors** (0 unsupported claims, 0 false abstentions, 0 wrong abstentions, 0 budget terminations).
- **Judge Requirement:** All end-to-end F1 claims must be scored by a validated judge calibrated on `data/judge_v2_claims.json` (~150 claims: 75 supported + ~75 same-subject 1-detail negatives) with **$\ge 85\%$ agreement** against an owner-labelled 30-claim blind sample (`owner_sample.json`).
- **Split Hygiene:**
  - Tune and iterate locally on `dev_v1` (20) $\to$ `dev_40` (40) $\to$ `dev_65` (65 tuning questions) + `heldout_55` (55 held-out questions).
  - Run `final_v3` (120) **at most once per promoted winner**.

---

## 2. Iteration Ledger

| Iteration | Handoff / Design | Scope & Changes | Key Measured Metrics | Status | Commit |
|---|---|---|---|---|---|
| **Phase 0** | `20261122-rag-phase0-infra` | Build `golden_final_v3.json` (120 frozen questions), `dev_v1.sha256.json` (20 dev questions), and `src/rag_agent/runner.py` (per-question checkpoints, sha256 guard, host capture) | 120 questions frozen (`68` single-hop, `24` multi-hop, `28` abstain); 0 exact leakage across splits | **DONE** | `791cf78`, `4f4660c` |
| **Iter 1 (Steps 0, 2–6)** | `20261122-rag-execution-plan` | Pinned `R0` retrieval baseline (`size` 200/40, MiniLM, ms-marco reranker) + 5 single-axis sweeps on `dev_v1` (`chunk_400`, `chunk_800`, `bge-small`, `qwen3-embed`, `Qwen3-Reranker-0.6B`) + `R0` baseline on `final_v3` | `dev_v1` `R0`: Recall@5 **1.0000**, MRR@5 **0.9688** (all 5 single-axis challengers tied Recall@5 1.0000 but regressed MRR to 0.9219–0.9531 $\to$ rejected).<br>`final_v3` `R0`: Recall@5 **0.9239** (85/92), MRR@5 **0.8793** (`single_hop` **0.9706**, `multi_hop` **0.7917**, abstain false-evidence **0/28**). | **DONE** | `1663dd3`, `7e3246a` |
| **Iter 1 (Step 1 — Rev 3 & 4)** | `20261122-rag-execution-plan` (Rev 3–4) | Draft 150 judge calibration claims (`75` supported + `75` unsupported). Rev 3 cross-topic negatives were too trivial (`150/150`). Rev 4 local 1-detail negative script hit self-8-gram collision & substring bugs. | 45+ `attempt1` local negative drafts cached on disk under `reports/judge_calibration_v2/drafts/`. | **FIXED IN REV 5** | `a419087` |
| **Iter 2 (Phase A)** | `20261122-rag-execution-plan` (Rev 5) & `20261123-rag-sota-retrieval-and-pipeline` | Patch `build_judge_calibration_v3.py` (cache-hit `attempt1`, exclude self 8-grams by claim text, word-boundary + digit check, retry feedback + temp/seed variation) $\to$ run `label_judge_calibration_v2.py` (`kimi-for-coding` $\le \$3.00$) $\to$ emit `owner_sample.json` (30 items with `chunk_text`). | Target: `75` supported + $\ge 70$ same-subject 1-detail negatives; owner 30-sample agreement $\ge 85\%$. | **READY FOR KIMI** | Pending execution |
| **Iter 2 (Phases B–D)** | `20261123-rag-sota-retrieval-and-pipeline` | SOTA Retrieval Ladder ($0 local):<br>- `S1`: `structure_200` (title-prefixed chunks)<br>- `S2`: `structure_hybrid_rrf` (`S1` + Dense-50 & BM25-50 RRF $\to$ Cross-Encoder top-30)<br>- `S3`: `structure_hybrid_diverse` (`S2` + per-article cap `max_per_article=2` in top-5)<br>Evaluated on `dev_v1`, `dev_40`, `dev_65`, `heldout_55` with `all_articles_at_5` + `recall_at_5` + `mrr_at_5`. Winning arm run **once** on `final_v3`, promoted to `src/rag_agent/`, plus agent loop bounds (`agent_tool_calls_limit=16`, `top_k` clamp). | Target: Lift `dev_65` from `53/55` (`0.9636`) to `55/55` (`1.0000`), lift `final_v3` `recall@5` from `0.9239` toward `>= 0.96+` and `multi_hop` from `0.7917` toward `>= 0.90+`, while keeping `n_abstain_false_evidence == 0`. | **READY FOR KIMI** | Pending execution |
| **Iter 3 (End-to-End S3)** | Planned (`20261123-rag-e2e-final-v3`) | Full 120-question `final_v3` agentic evaluation with promoted SOTA retriever, `agent_tool_calls_limit=16`, per-question checkpointing (`runner.py`), and validated judge (`judge_v2`), capped at $\$2.50$ soft / $\$3.00$ hard stop. | Target: Per-question F1 **0.85–0.90**, **0** budget terminations, **0** unsupported claims. | **GATED ON STEP 1 OWNER SAMPLE** | Planned |

---

## 3. Workflow Loop (Claude $\leftrightarrow$ Kimi)

1. **Claude** reviews results, architects the next iteration under `collaboration/designs/`, updates `collaboration/ITERATION_TRACKER.md`, validates gates, commits to git, and outputs the **Execution Snippet for Kimi**.
2. **Owner** pastes the snippet into Kimi's terminal.
3. **Kimi** executes the exact handoff steps, runs project gates, writes `collaboration/reviews/<handoff>/00-closeout.md`, and stops without committing.
4. **Claude** verifies the close-out report, runs repository validation gates, commits the verified implementation, and prepares the next iteration.
