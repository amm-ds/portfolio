# Master report for Kimi: review, web pass, SOTA ledger, and execution queue

Date: 2026-11-17
Author: Claude Code (review and design role)
Executor: Kimi Code (owner runs the session)
Status: final for this cycle. Nothing implemented by Claude. Execution is the owner's call.

## 1. How to use this report

1. Read section 2 (queue) to see what is approved and in what order.
2. Read section 4 before touching any number. Several copy figures in the repo were corrected by review and by primary-source checks.
3. Do not start a handoff marked "Owner decision required" beyond its stop condition. Write `OPEN_QUESTIONS.md` beside the handoff instead.
4. Every change follows `AGENTS.md` gates and `docs/engineering/code-quality-guidelines.md`. No git mutations. The owner commits.
5. Each finished handoff needs a completion report: exact files, commands, results, and remaining risks.

## 2. Execution queue

Approved handoffs, in recommended order. Each path is relative to the repo root.

| Order | Handoff | Why first | Blocked on |
|---|---|---|---|
| 1 | `collaboration/designs/20261117-metrics-guard-fix/03-implementation-handoff.md` | Production blocker: 02, 08, 11 show "Metrics could not be loaded". | Owner redeploys after the fix. |
| 2 | `collaboration/designs/20261117-10-uplift-review-fixes/03-implementation-handoff.md` | Blocker: copy says 64,000 customers; analysis uses 42,613. "Profit" is revenue minus send cost. | None. |
| 3 | `collaboration/designs/20261117-04-nlp-review-fixes/03-implementation-handoff.md` | Blocker: the cascade gain (+0.001 macro-F1) is within noise and must not be called a lift. | None. Do not re-run paid LLM calls. |
| 4 | `collaboration/designs/20261117-02-m5-review-fixes/03-implementation-handoff.md` | Selection-isolation test; single-origin caveat. | Reconciled LightGBM number must already be committed, or write an open question. |
| 5 | `collaboration/designs/20261117-06-routing-review-fixes/03-implementation-handoff.md` | Label the CP-SAT arm as not independent; add unhinted arm. | HGS / PyVRP comparator is an owner decision (not in this handoff). |
| 6 | `collaboration/designs/20261117-mobile-figure-layout/03-implementation-handoff.md` | Family_gap is unreadable at 375 px. | Per-row height change needs owner decision (stop condition). |
| 7 | `collaboration/designs/20261117-figure-review/03-implementation-handoff.md` | Figure fixes and PNG re-export for prod. | Still **draft**. Owner must approve before Kimi starts. |
| 8 | `collaboration/designs/20261117-12-tabular-review-fixes/03-implementation-handoff.md` | Tie-break wording must be confirmed first. | Owner confirms tie-break. |
| 9 | `collaboration/designs/20261117-13-serving-review-fixes/03-implementation-handoff.md` | p95/p99 with n; parity-gate test. | Standard load tool run needs owner approval. |
| 10 | `collaboration/designs/20261117-08-inference-review-fixes/03-implementation-handoff.md` | Guardrail framing; cost assumptions. | Harder quality task is an owner decision. |
| 11 | `collaboration/designs/20261117-05-churn-review-fixes/03-implementation-handoff.md` | Cost weights beside figures; holdout test. | Stop if cost weights are not in config. |
| 12 | `collaboration/designs/20261117-07-mobility-review-fixes/03-implementation-handoff.md` | Reconcile −28.2% vs −28.3%; name coverage outliers. | Stop if unrounded MAEs not committed. |
| 13 | `collaboration/designs/20261117-01-rag-review-fixes/03-implementation-handoff.md` | Judge and RAGAS version on card. | BM25 arm is an owner decision. |
| 14 | `collaboration/designs/20261117-03-anomaly-review-fixes/03-implementation-handoff.md` | Split headline; precision intervals. | NAB official scorer is an owner decision. |
| 15 | `collaboration/designs/20261117-11-dataeng-review-fixes/03-implementation-handoff.md` | Spread per cell; negative parity test. | ClickBench mapping is an owner decision. |
| 16 | `collaboration/designs/20261117-09-agentic-review-fixes/03-implementation-handoff.md` | Pass-rate intervals; legacy labels. | Live confirmation is a separate paid approval. Do not call the hosted endpoint. |

Note: the earlier `03-implementation-handoff.md` for the figure review (item 7) also says to re-export PNGs under `docs/assets/projects/` for prod. Prod is the mkdocs site and the showcase; both need the re-export.

## 3. Owner decisions

**Recorded 2026-11-18, approved for execution by the owner (apply these defaults):**

1. Routing comparator: run PyVRP on Solomon locally. Skip the vehicle-delta investigation for now.
2. NAB scorer: do not compute the official score. State on the card that it is not reported.
3. Harder quality task (08): deferred.
4. BM25 + reranker arm (01): deferred.
5. Live confirmation (09): the held-out run on `kimi-for-coding` under the $5 cap is approved. Further live runs are deferred.
6. Standard load tool (13): deferred.
7. Narrow-width height (figures): keep the 360 px per-row minimum. Fix the mobile layout with the legend change only.
8. Tie-break (12): call the MLP and LightGBM a tie on validation. Remove the champion label.
9. Cost weights (05): confirm they are in config before churn work. If not, that handoff stops.
10. ClickBench mapping (11): deferred.
11. TabPFN scope (12): use TabPFN-2.5 for the bike data.
12. M5 values (02): stay open.
13. Hillstrom Qini leaderboard (10): run the search, under one protocol, and report the result.
14. `quality_quant` on mkdocs (08): leave it off the page.

Where a decision changes a handoff's scope, the handoff's own stop conditions still apply.

**Previously open list (superseded where it conflicts with the above):**

These block the handoffs above. Kimi must not decide them.

1. HGS or PyVRP comparator for project 06, and whether to run the vehicle-delta investigation.
2. NAB official score for project 03: compute it with the official scorer, or state on the card that it is not reported.
3. Harder quality task for project 08.
4. BM25 + reranker reference arm for project 01.
5. Live confirmation budget and approval for project 09.
6. Standard load tool run (locust or wrk) for project 13.
7. Per-row minimum height change at narrow widths (`PlotlyFigure.tsx` `scaledHeight`).
8. Tie-break wording for project 12.
9. Whether cost weights for project 05 are in config. If not, project 05 stops.
10. ClickBench mapping for project 11.
11. TabPFN scope for project 12: TabPFN-2.5 (up to 50,000 rows) or TabPFN v2 on a documented subsample (v2 evaluation scope is up to 10,000 samples).
12. M5 WRMSSE values and reconciliation method for project 02. Left open by owner.
13. Hillstrom Qini leaderboard under one protocol for project 10. Not yet searched.
14. Whether `quality_quant` should appear on the mkdocs prod page (not in `DOCS_FIGURES`).

## 4. Verified facts and corrections (SOTA ledger)

Use these when writing copy. Anything not listed here is unverified.

| Topic | Fact | Source | Status |
|---|---|---|---|
| NAB v1.0 Standard scores | Numenta HTM 70.5–69.7 (seed range), CAD OSE 69.9, ARTime 74.9, Twitter ADVec v1.0.0 47.1, Etsy Skyline 35.7, Random 11.0, Null 0.0, Perfect 100.0 | github.com/numenta/NAB README (v1.0 scoreboard) | Verified |
| Earlier NAB claims | HTM 64.7 and random 16.8 are **not** the official table values. Do not quote. | Same | Corrected |
| SetFit AG News | Table 2: SetFit_MPNet N=8 82.9, N=64 88.0; FineTune (RoBERTa-Large) N=8 81.7, N=64 88.4, full 93.8 | arxiv.org/abs/2209.11055 | Verified |
| Bent and Van Hentenryck 2004 | 10 of 56 Solomon best-known solutions improved (17%); 46 matched or improved | Transportation Science abstract (pubsonline.informs.org/doi/fpi/10.1287/trsc.1030.0049) | Verified. The 2001 tech report's 13 of 58 is superseded. |
| PyVRP VRPTW results | Run on **1000-customer Homberger and Gehring** instances, not Solomon. Table 2: PyVRP mean gap 0.40%, HGS-DIMACS 0.32%, DIMACS reference 0.29%, BKS 0.00%. PyVRP improved 27 of 300 best-known. | arxiv.org/html/2403.13795v2 | Verified. No Solomon table exists in the paper. Solomon comparison must be run locally. |
| TabPFN Nature 2025 | 28 regression datasets, up to 10,000 samples and 500 features. Normalised RMSE: default 0.923 vs CatBoost 0.872; tuned 0.968 vs 0.875. Paper: "scalability to larger datasets requires further study." | Europe PMC PMC11711098 | Verified for the stated text. Raw values in an image table not read. |
| TabPFN-2.5 | Reported up to 50,000 rows, 2,000 features | arxiv.org/pdf/2511.08667 (secondary summary) | Secondary |
| M5 citation | Makridakis, Spiliotis, Assimakopoulos, IJF 38(4): 1346–1364 (2022), DOI 10.1016/j.ijforecast.2021.11.013 | econpapers / IDEAS listing | Citation verified. WRMSSE values of top entries **open**. |
| M5 top entry (secondary) | 1st-place Accuracy entry used direct and recursive LightGBM | Secondary summaries | Secondary. 0.52 score and reconciliation method **unverified**. |
| Anderer and Li (M5 2nd) | Top-down alignment of independent level forecasts | arxiv.org/pdf/2103.08250 | Source-backed (search summary) |
| Wellens et al. IJF 2022 | Transfer learning on store-level LightGBM: similar accuracy, ~25% less training time | ideas.repec.org | Source-backed (search summary) |
| Grinsztajn et al. | Tree ensembles remain strong on medium tabular data (~10k samples) | arxiv.org/abs/2207.08815 | Source-backed (search summary) |
| τ-bench | GPT-4o: 61.2% retail, 35.2% airline at pass^1; pass^8 below 25% on retail | Sierra blog | Source-backed (search summary) |
| Hillstrom | 64,000 customers, three arms (men's email, women's email, control) | Paper description, arXiv 2003.11940 | Secondary |
| UpliftBench (Criteo) | S-learner highest on Qini; causal forest low, attributed to subsample size | arxiv.org/abs/2604.06123 (preprint, 2026) | Secondary. Criteo, not Hillstrom. |

## 5. Corrections to earlier review files

Apply these when editing copy or reports. They supersede the review text where they conflict.

1. **Project 10 (uplift):** short copy must say 42,613 customers analysed within the 64,000-row dataset. "Profit" means revenue minus send cost; rename everywhere. "+69%" is 69.9%; show +70% or one decimal.
2. **Project 04 (NLP):** the cascade gain is +0.001 macro-F1 on 1,000 fresh items with 22 reviews. Report as "no measurable change" unless a paired interval excludes zero. Round copy to three decimals. The int8 row is measured on a different split; do not compare directly.
3. **Project 07 (mobility):** −28.2% vs −28.3% depends on unrounded values. Use one value everywhere.
4. **Project 06 (routing):** the `ortools_cp` row is seeded from ALNS and is not independent. The PyVRP paper has no Solomon results. Do not quote PyVRP gaps for Solomon.
5. **Project 12 (tabular):** the bike dataset has 17,379 rows, above the TabPFN v2 evaluation scope (10,000). Use TabPFN-2.5 or a documented subsample. The MLP vs LightGBM difference is a tie on validation (0.2 MAE); do not call the MLP the champion without a paired interval.
6. **Project 03 (anomaly):** quote NAB v1.0 values from section 4 only. Recommend VUS-PR alongside range-F1 (TSB-AD recommendation).
7. **Project 02 (M5):** do not quote a top-solution WRMSSE. The public value is open.

## 6. Web-pass findings (production, 375 px)

Source: `collaboration/reviews/20261117-web-pass/01-web-pass-and-visuals.md`

- Metrics error: 02, 08, 11. Root cause: `getMetrics` guard in `apps/showcase-web/src/api.ts:96`. Fix in metrics-guard handoff; it must also be redeployed.
- No horizontal page overflow at 375 px on the pages checked.
- Figures render lazily when scrolled into view. "rendering figure…" is not a defect.
- Family_gap (06) is unreadable on mobile. Fixed by the mobile-figure-layout handoff.
- Desktop layout was not checked (the browser pane could not restore a desktop width). Owner decision whether to re-check.

## 7. Per-project review files

All in `collaboration/reviews/20261117-experiment-review/`. Index: `00-index.md`. Each lists verdict, architecture, metrics, visuals, copy, and ordered tasks with severity.

Research and recommendations: `collaboration/reviews/20261117-sota-research/00-research-and-recommendations.md`. Confidence labels: source-backed, secondary, hypothesis. Section 4 of this report supersedes it where they differ.

## 8. Gates (from AGENTS.md)

Run the gates each handoff names. Full set when a change touches several areas:

```bash
uv sync --all-packages --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run pytest -q                      # or the affected suites
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict          # after docs edits
```

## 9. Rules for Kimi

- Stay inside the approved handoff's scope. If scope is missing or contradictory, write `OPEN_QUESTIONS.md` beside the handoff and stop.
- Do not change generated registries by hand. Regenerate with their scripts.
- Do not call paid or hosted model endpoints unless the owner has approved that specific run.
- Do not run git mutations.
- Report exact files changed, commands run, results, and remaining risks. Quote numbers exactly.
