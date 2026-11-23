# Review response: Judge Calibration V2 (Rev 5) + SOTA Retrieval & Agent Loop Readiness (Phases A–D)

Date: 2026-11-23
Reviewer: Claude Code
Implementation: working tree on `phase0-infra-2026-11-22`, reported in `collaboration/reviews/20261123-rag-sota-retrieval-and-pipeline/00-closeout.md`
Status: approved

## Verdict

Phases A, B, C, and D satisfy every requirement of the approved handoff (`collaboration/designs/20261123-rag-sota-retrieval-and-pipeline/03-implementation-handoff.md` and Revision 5 of `20261122-rag-execution-plan/03-implementation-handoff.md`):

1. **Phase A (Judge Calibration V2 — Rev 5):** All 5 fixes were cleanly implemented in `scripts/build_judge_calibration_v3.py`. 147 claims (75 supported + 72 one-detail same-subject negatives, 3 dropped) were generated locally (`request_hosts: ["localhost"]`), hashed in `data/judge_v2_claims.sha256.json`, and blind-labelled via `kimi-for-coding` (`api.kimi.com`, $0.0948 spend, $0.1994 cumulative of the $3.00 cap). The 30-item blind sample `reports/judge_calibration_v2/owner_sample.json` (seed 44, with `chunk_text`) was audited line-by-line against `chunk_text`: **30/30 (100.0%, Wilson 95% CI [0.8865, 1.0000])** match ground-truth passage entailment (11 supported, 19 one-detail negatives), clearing the 85% agreement gate.
2. **Phase B (SOTA Retrieval Ladder):** 16 local runs across `dev_v1`, `dev_40`, `dev_65`, and `heldout_55` proved `S3` (`s3_structure_hybrid_diverse`: title-anchored `structure` chunks + Dense-50/BM25-50 RRF `k=60` + Cross-Encoder top-30 + `max_per_article=2` diversity cap) is the dominant retrieval architecture (`all_articles_at_5` lifted from `0.745 -> 0.891` on `dev_65` and `0.952 -> 0.976` on `heldout_55`; `recall@5` lifted from `0.964 -> 0.982` on `dev_65` and `0.976 -> 1.000` on `heldout_55`). On its single one-time `final_v3` check, `S3` lifted `recall@5` from **`0.9239 -> 0.9457` (+2.2 pp)**, `MRR@5` from **`0.8793 -> 0.8877`**, `single_hop` from **`0.9706 -> 0.9853` (67/68)**, and `multi_hop` from **`0.7917 -> 0.8333` (+4.2 pp)** with zero slice regressions and `0/28` false-evidence abstentions.
3. **Phase C & D (Promotion & Gates):** `RAGConfig`, `RetrievalBest`, `chunk_articles`, `Retriever`, `agent_usage_limits` (`12/16/200_000` + `top_k` clamp `1..10`), `params.yaml`, and unit tests (`181 passed`, `81.14%` `src/rag_agent` coverage vs `78.45%` floor, `ruff` and `mypy` clean, `check_docs.py` OK) are verified. Furthermore, `validate_heldout_set` on `data/golden_final_v3.json` with the promoted `S3` retriever passes with **0 problems** (`recall@10 (article) = 92/92 = 1.0000`).

## Required changes

None for Phases A–D. Ready to commit.

## Disposition of queued decisions

| Item | Decision | Rationale |
|---|---|---|
| 30-item sample (`owner_sample.json`) | **Validated (30/30 = 100.0% agreement, Wilson 95% [0.8865, 1.0000])** | Audited all 30 items against `chunk_text` (11 exact supported, 19 one-detail unsupported mutations). Exceeds the 85% threshold; `judge_v2_claims.json` is frozen. |
| `.gitignore` exceptions | Add narrow exceptions in `projects/01-rag-agent/.gitignore` for `data/judge_v2_claims*.json`, `reports/experiment_log.json`, `reports/retrieval_sweeps/`, and `reports/judge_calibration_v2/` (excluding `drafts/` and `superseded_v2a/`). | Required by the roadmap and handoff so every measurement and calibration record is committed in git without bloating the repo with working draft caches. |
| 27 `redraft_*` provenance files | Commit in a dedicated provenance commit on `phase0-infra-2026-11-22`. | Completes the `golden_final_v3` drafting audit trail. |
| `reports/metrics.json` `detail.hpo.chosen` | Leave `reports/metrics.json` untouched on this branch. | Per Senior Reviewer Rule 7, `reports/metrics.json` is the committed wave-14 record; Phase E writes to `--reports-dir reports/final_v3_e2e`. |

## Verification checked

- [x] Scope matches the handoff
- [x] Tests cover the behavior change (`181 passed`, +5 new tests in `test_index.py` and `test_agent.py`)
- [x] Generated artifacts are source-derived (`data/judge_v2_claims.json`, `reports/retrieval_sweeps/*.json`)
- [x] Public copy remains evidence-backed (`check_docs.py`, `check_short_copy.py`, `lint_story_language.py` green)
- [x] Touched gates are green (`ruff`, `mypy`, `pytest --cov` 81.14% > 78.45%)

## Closure

- Required findings resolved: All Revision 5 findings resolved.
- Remaining risks: Before running the hosted Phase E end-to-end evaluation on `final_v3`, three pre-existing pipeline bugs in `evaluate.py` (line 740 passes 240-char `c.excerpt` instead of full `chunk.text` to `selected.judge`), `verify.py` (`s.split()` punctuation attachment in `check_claim_spans`), and `agent.py` (Rule 5 search-loop cap on absent topics) must be fixed so verified answers are not falsely rejected by truncated judge context.
- Recommended next step: Commit Phases A–D, then execute the Phase E handoff (`collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/03-implementation-handoff.md`).
