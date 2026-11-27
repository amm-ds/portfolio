# Grade pass 5 — final result and 14-project grade table

Date: 2026-11-26. Branch: `wave8-articles-truthfulness-2026-11-25`.
Grades are the plan's four axes (Content / Results / Technologies /
Visualizations) with the plan's overall; before = pass-4 entry grades.

## Phase commits

| phase | commits | result file |
|---|---|---|
| 1 (E9, 02 refit) | `51997c87` (+ shared-surface copy in `b7568ffb`) | agent report; reproduction byte-exact |
| 2 (01 final_v4 + judges) | `606587f8` | `phase-2-result.md` |
| 3 (12 scratch rerun) | none (scratch only) | `phase-3-result.md` |
| 4 (12→13 v2 promotion) | `405d579c`, `a46cf5f3`, `96b25cbb`, `34f59274`, `4e20a2b4` | `phase-4-result.md` |
| docs handoff | `b7568ffb` | `../20261126-grades-pass-4-plan/02-kimi-docs-result.md` |
| 5 (copy sweep) | the mypy fix commit (see phase 6) | `phase-5-result.md` |
| 6 (verification) | — | `phase-6-result.md` (gate exit codes) |

Hosted spend this pass: **$1.19** (Phase 2c) — cumulative pass-4+5 hosted
spend **$1.60 of the $5.00 cap**.

## Final grade table (14 projects; there is no project 14)

| project | before (pass 4) | after | per-axis after | what moved it / what capped it |
|---|---|---|---|---|
| 01 RAG agent | 8.3 | **8.8** | 9/9/8/9 (T capped at 8) | C/V fixed in pass 4. T capped: the final_v4 rerun's replication F1 is 0.8466 against the committed 0.9091 (gap −0.0625, dominated by 24 loop-rail terminations vs 4 committed) — the committed 0.9091 headline stays while the fresh rerun disagrees, and the only cross-family judge is a local 3B (weak, κ 0.09 answered). Disclosure committed; a hosted non-Moonshot key is the remaining path |
| 02 Demand forecasting | 8.0 | **9.0** | 9/9/9/9 | E9 refit reproduced the blend byte-exact (Δ 0.0); demo serves 0.6211; headline level CI [0.5588, 0.6974]; sample-series figure restored |
| 03 Anomaly detection | 8.3 | **9.0** | 9/9/9/9 | Official NAB score published (51.45 standard / 49.81 low-FP / 62.46 low-FN, vendored MIT scorer, null 0 / perfect 100 exact); 0.527 collision resolved; champion wording gone |
| 04 NLP classification | 8.0 | **9.0** | 9/9/9/9 | E6 paired CI [−0.0081, +0.0060] + McNemar p = 1.000 published beside the committed number; gain stated as not distinguishable from zero |
| 05 Churn pipeline | 8.3 | **9.0** | 9/9/9/9 | E3 20-split selection uncertainty (median −$392, [−$439, −$340]); committed split inside on the favorable side; threshold-selection caveat in copy |
| 06 Routing optimization | 8.8 | **9.0** | 9/9/9/9 | 5-vs-8 count fixed with the −0.005% tie threshold; finding titles |
| 07 Mobility | 8.5 | **9.0** | 9/9/9/9 | E2 served-model paired CIs (day-block + zone-cluster, all four comparisons exclude zero); coverage persisted at `analysis.p90_coverage` |
| 08 Inference serving | 7.8 | **8.8** | 9/9/8/9 | C/V fixed in pass 4; T capped at 8: E10 stopped at its re-measurement gate (+20.5%/+6.0% drift, Ollama 0.40.4→0.40.17, co-tenant load); owner accepted 8.8 on one host, 2026-11-27. The E10 harness is committed and ready for a quiet window |
| 09 Agentic workflows | 8.3 | **9.0** | 9/9/9/9 | E7 five live repeats: pass^5 = 17/19 disclosed everywhere (per pass-3 P2.2, the honest repeat result is still T9); first-contact copy fixed |
| 10 Uplift experimentation | 8.0 | **9.0** | 9/9/9/9 | E1 CIs persisted in `metrics.json` `analysis.ci`, bit-identical to 0c01c45d, gated from both files; qini axes fixed; 12.03 two-interval wording resolved |
| 11 Data engineering | 8.8 | **9.0** | 9/9/9/9 | Finding titles (Phase C) |
| 12 Tabular lifecycle | 8.0 | **9.0** | 9/9/9/9 | Option B promoted: v2 fixes both disclosed defects; corrected MLP worse (27.16 vs 25.43) stated plainly; LightGBM better (23.76) and now served; v1 under `previous_runs.v1` |
| 13 Model serving | 8.5 | **9.0** | 9/9/9/9 | Regenerated from v2 with LightGBM: reproduction diff 0.0; ONNX parity max-abs 2.65e-4 against the gate of 1e-4 rentals plus a float32 term of 1e-5 × largest prediction (limit 6.8e-3) — above the bare 1e-4, would fail without the term (owner accepted 2026-11-26); image 6.5 GB → 1.06 GB (torch dropped); p50 2.0 ms |
| 15 Dynamic pricing RL | 9.0 | **9.0** | 9/10/9/8 | Pass-4 diagram specs + fence gate landed. Note: 9.3 pending the orchestrator's browser check of the five diagrams at deploy |

**Portfolio: 12 of 14 at 9.0; 01 and 08 at 8.8 with the caps disclosed in
their Limits sections.**

## Downgrades / non-promotions (causes)

- 01 stays 8.8 — Phase 2 outcome rule failed on both legs (replication gap
  −0.0625 > 0.03; cross-family κ 0.55 < 0.6, and the cross-family judge is
  weak evidence by construction). Not a downgrade: the pass-4 entry was 8.3.
- 08 stays 8.8 — E10's stop rule fired; no quality-axis evidence was added.
  08: axes 9/9/8/9 give 8.8 by the overall formula. Owner decision 2026-11-27: keep 8.8 on one host (T capped at 8).
- 15 stays 9.0 in this table — the 9.3 browser check belongs to the deploy
  step (orchestrator), not to a commit.

## Not done / follow-ups

- E12's 13-side was completed inside Phase 4 (13 regenerated from v2). The
  separate "retrain as v2" question is closed by the promotion.
- 04 `dvc.yaml` still declares the cascade metrics file the stage never
  rewrites (cosmetic; recorded).
- 12 `dvc.lock` is stale until 01's dvc.yaml overlap is fixed (recorded by
  the Phase 4 agent; cosmetic for reproducibility of the committed
  artifacts, which are hash-pinned in evaluation_metadata).
- A hosted cross-family judge for 01 needs a non-Moonshot key in `.env`.
- E10 re-attempt needs a quiet window (the 3-day VM and sidecar processes
  on this host saturate CPU); the harness is committed.
