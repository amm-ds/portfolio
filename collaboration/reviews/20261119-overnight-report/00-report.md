# Overnight queue report — 2026-11-19

Executor: Kimi Code (per `collaboration/designs/20261118-overnight-kimi/00-overnight-brief.md`)
Designer handoffs: `collaboration/designs/20261117-*` + `20261118-live-confirmation-09`
No git mutations performed. No deploys. `.env`/permissions/config untouched.
The only hosted calls were item 15's single approved run ($0.094112 of the $5 cap).

## Summary table

| # | Item | Status | Key results |
|---|---|---|---|
| 1 | Metrics guard (web) | done | Guard relaxed to any top-level object; consumers hardened; new tests; 02/01/08 verified in browser locally |
| 2 | 10-uplift copy | done | 42,613 of 64,000; "revenue minus send cost" throughout; +70%; policy rule sentence; 2 new tests |
| 3 | 04-NLP cascade interval | blocked (documented) | Per-row LLM decisions not committed → interval not computable offline; copy reworded to "no measurable change" per correction 2; OPEN_QUESTIONS.md written |
| 4 | 02-M5 selection isolation | done (1 sub-item blocked) | Isolation test added (passes; fails on injected test-origin read); caveat beside 0.6161; reconciled-LightGBM row: number not committed → OPEN_QUESTIONS.md |
| 5 | 06-routing labels + PyVRP | done (1 interval blocked) | "ALNS-hinted; not independent of ALNS" everywhere; mean-gap bootstrap CI [3.22, 5.28]% committed; unhinted arm honest; ALNS-vs-unhinted interval null (no distances) + OPEN_QUESTIONS.md; PyVRP 0.14.1 run: mean gap −3.71% vs committed refs, 8.62 vehicles, 15 s/instance |
| 6 | Mobile figure layout | done | Theme-default right legends move below plot < 600 px (ECharts converter + Plotly fallback); measured before/after; 360 px minimum untouched |
| 7 | 12-tabular tie + TabPFN | done (TabPFN blocked) | Validation tie interval −0.18 [−1.71, +1.21] committed; champion label removed; selection-isolation test; TabPFN 10.2.0 needs license/token → OPEN_QUESTIONS.md |
| 8 | 13-serving p95/p99 + n | done | Headline/figure/story carry p95 2.0 ms, p99 2.2 ms, n = 300/cell; parity test pre-existed |
| 9 | 08-inference labels/cost | done | Quality table titled "Saturated smoke check — ties 1.00; not quality"; $0.12 traced (67.7 tok/s measured, 100 W, $0.30/kWh); percentile/cost tests pre-existed |
| 10 | 05-churn cost weights | done | Weights confirmed in config (fp 1.0 / fn 5.0); stated beside 601/1,035; threshold marker pre-existed; holdout-isolation test added |
| 11 | 07-mobility rounding | done | Unrounded 28.250002% → −28.3% confirmed correct and consistent (a hair above the .25 tie); coverage outliers in headline; card says "persistence floor"; test-MAE poisoning test |
| 12 | 01-RAG metadata | done | judge_model kimi-for-coding + ragas_version 0.3.1 committed in metrics.json + card/README; stress "5 of 30 (was 11 of 30)" + CI note; axis n on both figures |
| 13 | 03-anomaly headline/intervals | done | Card split raw/budgeted + "NAB official score not reported" (decision 2); precision CI [0.231, 0.811] committed (series bootstrap, 2000, seed 42); README definitions table |
| 14 | 11-data-eng spread + parity | done | time_min/max_s for 99 cells from recorded repeats (values unchanged otherwise); ladder formula stated (geomean ×19.2/×14.9 verified); negative parity test |
| 15 | 09 held-out live run | done | 1 run, ledger $0.094112 of $5; 13/13 answers, 6/6 refusals, 19/19 budgets live vs 13/13, 5/6, 18/19, 12/19 legacy; comparison.md written |
| 16 | 09 pass-rate intervals | done | Wilson intervals committed (tuning + heldout); "legacy recorded run" labels on report + 4 figures; run-once stated on card + README |
| 17 | Hillstrom Qini search | done | No public one-protocol leaderboard exists; findings + sources in `collaboration/reviews/20261117-sota-research/13-hillstrom-qini-search-2026-11-19.md` |

## Details per item

### 1. Metrics guard — done
- Files: `apps/showcase-web/src/api.ts` (`Metrics = Record<string, unknown>`, guard = `isRecord` only), `components/MetricsTable.tsx` and `lib/delta.ts` (record-guarded consumers), tests in `__tests__/api.test.ts` (new payload-with-list test fails pre-change, passes post; non-object rejection kept), `__tests__/FlowDiagram.test.tsx` (one expectation updated to the final mobile contract: zoom 1 at 390 px — pre-existing uncommitted diagram work, verified).
- Commands: `npm test` (746 passed), `npm run lint`, `npm run build`, `uv run pytest -q apps/showcase-api` (102 passed).
- Browser check (playwright, local dev → API :8002): `/projects/02-demand-forecasting`, `/projects/01-rag-agent`, `/projects/08-inference-serving` — no "Metrics could not be loaded" box.
- Prod NOT redeployed (owner's job per brief).

### 2. Uplift copy — done
- `story.yaml` short_version (274 chars): 42,613 customers (Men's E-Mail vs No E-Mail) from the 64,000-row Hillstrom dataset; +70% (choice: +70%, 2,812/4,026 = 69.9%).
- "profit" → "revenue minus send cost" in README (headline sentences + labels), figure titles/axes (evaluate.py), demo note, docs page/index/root README rows. JSON keys (`profit_frontier`, `profit_at_budget`, …) unchanged per handoff.
- Policy rule sentence added (README): selection by revenue minus send cost at the 25% budget; response model not chosen despite nominally higher Qini (paired interval overlaps).
- New tests: `tests/test_policy_selection.py` (adversarial + reference-curve exclusion; a Qini-based rule picks the wrong model on the same input — demonstrated); `test_cuped.py::test_variance_reduction_matches_closed_form` (exact 0.8 construction; no-op adjustment → 0).
- Regenerated: figures (evaluate), demo_payload.json (1-line note change), metrics.json (provenance-only diff after stamp), report.html, storyShort.ts.
- Remaining "profit": story.yaml body/figure captions + MODEL_CARD/DESIGN/portfolio.yaml — out of the handoff's stated scope (flagged for owner).

### 3. NLP cascade interval — BLOCKED (OPEN_QUESTIONS.md written)
- `llm_cascade.json` carries split aggregates only; the 22 per-row LLM decisions on the fresh 1,000 are not committed anywhere; recomputing needs paid calls (forbidden). Paired interval not identifiable from committed artifacts.
- Per master-report correction 2, copy reworded to "no measurable change (Δ macro-F1 +0.001)": short_version (272 chars), README, story body/captions, docs surfaces, root README/docs rows; licence → "research purposes" (dataset card); int8 row moved to a separate "train-sample quality" table (option b); routing boundary test added (strict `<`; fails under `<=`).
- Gates: 85 tests passed; ruff/mypy/short-copy/docs/lint green.

### 4. M5 selection isolation — done, step 2 blocked
- New test `test_screened_ensemble_never_reads_test_origin`: sentinel `wrmsse_fn` on the test origin never fires during selection; members/weights/blend identical vs benign run; injected read (selection=[0,1,2]) trips the sentinel. Full 02 suite: exit 0 (all pass).
- Caveat "One scored test origin; no bootstrap interval" as table footnote beside 0.6161 + short_version.
- Reconciled global LightGBM: only UCI-hierarchy reconciliation artifacts are committed; nothing for the M5 full panel → OPEN_QUESTIONS.md (step 2 stop condition).
- Rounding verified: −31.0% and all table values unchanged; `_num` test helper now tolerates footnote markers.

### 5. Routing labels + PyVRP — done, one interval blocked
- `solver_display_name` in reporting.py labels every `ortools_cp` table mention "ALNS-hinted; not independent of ALNS" (results.md regenerated; README/DESIGN/story carry the full phrase).
- `metrics.json` gains `intervals.mean_gap_pct` = point 4.2322, 95% CI [3.2232, 5.2815] (56-instance bootstrap, 2,000 resamples, seed 42) + `alns_vs_unhinted_cp_sat` recorded as null with reason (all 56 unhinted cells UNKNOWN, no distances) + OPEN_QUESTIONS.md.
- Unhinted arm promoted honestly in README/story (no feasible plan on any of 56; runtime 13.1 s).
- Tests: determinism (same seed identical; different seed differs; point 28.5 inside CI), null-recording, label presence in all three tables.
- PyVRP (decision 1): dependency added to project 06 (uv.lock updated); 56/56 instances at 15 s/instance, seed 42: mean gap −3.7145% (55/56 at or below committed best-known), mean 8.62 vehicles, mean runtime 15.006 s. Model built from the project's own parser; "exact" ×1000 convention; return-by-horizon via shift duration; C101 reproduces the published optimum 828.94 exactly (recorded 828.937). Results: `collaboration/designs/20261117-06-routing-review-fixes/pyvrp-solomon-results.json` (routes persisted; validation note: pyvrp's internal feasibility flags all True; an independent schedule-idx re-walk hit an extraction-ordering mismatch, so per-route lists are advisory — see the file's `validation` block). Surfacing PyVRP into the README ladder is an owner decision (new solver arm).

### 6. Mobile figure layout — done
- Measured BEFORE at 375 px: card 930×335, plot box 720×317 (two rows × 360 px minimum); legend right, capped ~46% band. AFTER: same card height (360 px minimum untouched per decision 7), legend horizontal in wrapped rows below the plot, panels use full width; 1024 px unchanged (screenshots: /tmp/family_gap_before_w{375,1024}.png, /tmp/family_gap_after2_w{375,1024}.png).
- Implementation: `NARROW_LEGEND_BREAKPOINT = 600` in `plotlyToECharts.ts` (theme-default right legend signature x=1.02/xanchor=left relocates below; right margin freed; legend row height estimated from wrapped rows) + the same rule in `PlotlyFigure.buildLayout` (fallback path, margin r → 8, +60 px height). Generator-positioned legends keep their authored position at every width.
- Tests: 3 new converter tests + 3 new buildLayout tests; one pre-existing mobile test updated to the new contract. Web suite: 746 passed.

### 7. Tabular tie + TabPFN — done, TabPFN blocked
- Paired validation interval committed top-level in metrics.json (survives the stamp convention): MLP − LightGBM = −0.1798, 95% CI [−1.7054, +1.2134], 2,000 resamples, seed 45 — spans zero → tie (decision 8). "champion" removed from README/story (12 spots) → "served model / validation pick, tied"; tie stated beside the results table; selection test (sentinel test scores + poisoned extra keys cannot move selection; signature guard).
- residual_heatmap: colorbar "mean residual (rentals)" confirmed — no fix needed.
- TabPFN-2.5: tabpfn 10.2.0 gates model-weight download behind a Prior Labs license + `TABPFN_TOKEN` (account-bound) → cannot proceed without the owner → OPEN_QUESTIONS.md (3 options listed, script preserved at /tmp/tabpfn_bike.py).

### 8. Serving tail latency — done
- Committed bench artifact already carried p95/p99; metrics.json cells verified (c1 native p50 0.0016 / p95 0.0020 / p99 0.0022 s, n=300). README headline + story headline/summaries/bullet now state p95 2.0 ms, p99 2.2 ms, n = 300/cell, nearest-rank; figure takeaway now labels n; latency_concurrency_lines regenerated. Parity-gate test pre-existed (perturbed fixture > 1e-4 raises; boundary at tolerance passes). Gates: 09... 13 tests exit 0; ruff/mypy/copy/docs green.

### 9. Inference labels + cost — done
- fig_quality_quant title: "Saturated smoke check — ties 1.00; not quality" (regenerated); README figures split headline vs detail with the saturated label; story caption updated.
- $0.12/1M assumptions stated beside the figure: measured 67.7 aggregate output tok/s (committed cell), declared 100 W system draw + $0.30/kWh (config defaults) — $0.1231 recomputed ≈ $0.12 ✓.
- Percentile + cost tests pre-existed with boundary + worked example (verified by reading + suite).

### 10. Churn cost weights — done
- Weights in config: fp_cost 1.0, fn_cost 5.0 (params.yaml + config.py) — stop condition not triggered.
- README key finding + story bill box now state "$5 per missed churner, $1 per contact (params.yaml)"; figure already carried the weights on the y-axis and the frozen-threshold star + annotation.
- New holdout-isolation test: sentinel holdout labels never passed; argmin consistent; all-zero labels would flip the optimum (not vacuous); signature guard.

### 11. Mobility rounding — done
- Unrounded: naive_lag24 6.517490660078139, gbm_tuned 4.676299418090131 → reduction 28.2500020025…% → **−28.3%** (a hair above the .25 tie; rounds up). Copy was already correct at 28.3 everywhere; no stray 28.2 exists. (I briefly blanket-replaced to 28.2, caught the arithmetic error, and reverted — final diff for 07 is wording-only.)
- Coverage outliers named in the story headline sentence (90.8% overall; no-borough 84.7% under; Staten Island 98.5% over); README already had them.
- Card: "28.3% vs the persistence floor" (278 chars); selection test added (poisoned test_mae favoring the challenger cannot move the served arm; validation still drives).
- Full 07 suite exit 0.

### 12. RAG metadata — done
- metrics.json top-level: `judge_model: kimi-for-coding` (from committed kimi_comparison.json) + `ragas_version: 0.3.1` (locked); writer updated so future runs carry them; README table + story paragraph cite both with their sources.
- Stress wording: "5 of 30 unsupported (was 11 of 30)" + "not a demonstrated gain" in README, story conclusions, and short copy (275 chars) with all copy surfaces synced.
- Axis n: retrieval_funnel regenerated honestly from committed traces (identical bars [54, 11]); failure_taxonomy label-only patch (bars [46, 2, 17, 0] preserved — a full regen would have reclassified counts, so only the axis title changed).
- No model calls.

### 13. Anomaly headline + intervals — done
- short_version (278 chars) split: (a) raw 16/17 + 1,609 alerts; (b) budgeted 80 pages + like-for-like 66→35 pages at recall 0.604, range-F1 0.533; "NAB official score not reported" on the card (decision 2).
- `pa_k_2_precision_interval` committed: point 0.5274, 95% CI [0.2305, 0.8107] — series-level bootstrap (resample the 9 evaluable series, macro-mean per draw; 2,000 resamples, seed 42); existing no-skill band untouched; `cli nab` reproduces the committed metrics byte-identical apart from the new block; figures byte-identical.
- README: interval cited + metric definitions table (range recall / precision / range-F1 / range-PR area × configuration) + not-reported rationale.
- Full 03 suite exit 0.

### 14. Data-eng spread + parity — done
- metrics.json gains time_min_s/time_max_s for all 99 cells (derived from the committed five warm repeats; semantic diff = spread + provenance only); writers updated for future runs; task_times_dotplot already drew min/max whiskers and the sqlite n/a takeaway.
- Ladder total stated: ×19.2/×14.9 = geometric mean of per-task median speedups vs pandas (polars 19.157, duckdb 14.886 verified from committed cells); totals row = plain sum.
- Negative parity test: one changed int row, one float beyond tolerance, dropped row all fail rows_equal; within-cliff float passes (documents the tolerance).
- One determinism test needed its timing-strip list extended for the new keys; 46 tests exit 0.

### 15. Held-out live run — done
- Pre: 09 working tree clean; previous run.log moved to run.log.previous.
- Command exactly as handed off. Result: exit 0, "run-all complete"; ledger: **50 metered calls, 96,166 in + 11,984 out tokens; estimated spend $0.094112 of $5.0 suite cap** — no cap warning, no auth/quota errors.
- Records: 19 (13 ok answers, 6 refused probes). Offline grading into collaboration/reviews/20261118-live-confirmation/live-grading (no committed path touched).
- comparison.md rows (live vs legacy): answers 13/13 vs 13/13; refusals 6/6 vs 5/6; step 19/19 vs 18/19; latency 19/19 vs 12/19; deadline cancellations 0/19 both.

### 16. Pass-rate intervals — done
- `wilson_interval` + `_pass_rate_intervals` in report.py (Wilson score, z=1.96; closed form, boundary-safe — method stated in docstring).
- metrics.json: tuning `detail.pass_rate_intervals` (15/15 → [0.7961, 1.0]) and heldout `detail.heldout.pass_rate_intervals` (13/13 [0.7719, 1.0]; 5/6 [0.4365, 0.9699]; 18/19 [0.7536, 0.9906]; 12/19 [0.4104, 0.8085]).
- Labels: report title + 4 figure titles + suite-summary takeaway carry "legacy recorded run"; card + README state each task ran once.
- Test: 15/15 vs hand-computed 0.7962; 12/19 midrange; zero-count safety; labels present in generated report. Offline regen only (no model calls).

### 17. Hillstrom Qini search — done
- `collaboration/reviews/20261117-sota-research/13-hillstrom-qini-search-2026-11-19.md`: under the stated one protocol (Mens-vs-control, conversion, out-of-fold Qini), no public comparable number exists; closest rigorous source = Hu/de Haan/Skiera DMKD 2024 (14 models, 100 bootstraps, AUUC ranks); UpliftBench's Qini/effect-accuracy caveat cited. Card implication stated; no code changed.

## End-of-night gates

- `uv run ruff check .` — All checks passed (749 files).
- `uv run ruff format --check .` — already formatted.
- `uv run mypy libs projects apps` — Success, no issues (233 files).
- `uv run pytest -q` (full repo) — **exit 0, 97.69% total coverage** (1,822 statements; every touched project's suite also passed individually during the night: 01 exit 0, 02 exit 0, 03 exit 0, 04 85 passed, 05 exit 0, 06 exit 0, 07 exit 0, 08 exit 0, 09 exit 0, 10 69 passed, 11 46 passed, 12 exit 0, 13 exit 0).
- Web: `npm ci` clean + `npm test` 746 passed (53 files), `npm run lint` clean, `npm run build` ✓.
- `lint_story_language` 0/0; `check_docs` OK; `check_short_copy` single-sourced (39 surfaces); `check_demo_contract` OK; `gen_static_registry --check`, `gen_story_short --check`, `gen_route_manifest --check` all current.

## Held-out run ledger line (verbatim)

`ledger: 50 metered calls, 96,166 in + 11,984 out tokens; estimated spend $0.094112 of $5.0 suite cap (cloud-equivalent, labelled estimate)`
Total hosted spend this session: **$0.094112 cloud-equivalent** (single approved run). No other hosted calls were made.

## Generated outputs written (paths)

- Regenerated artifacts: projects 02/06/08/09/10/11/12/13 metrics.json (+ figures/report.html where applicable), all with the repo's provenance-stamp convention restored.
- New result records: `collaboration/designs/20261117-06-routing-review-fixes/pyvrp-solomon-results.json`; `collaboration/reviews/20261118-live-confirmation/{heldout_live_records.json, run.log, live-grading/metrics.json, comparison.md}`.
- OPEN_QUESTIONS.md beside handoffs 02, 03(NLP), 06, 07(12-tabular).
- This report.

## Dependencies added (uv.lock grew by 157 lines)

- `pyvrp==0.14.1` (+vrplib) to projects/06 (decision 1 comparator).
- `tabpfn==10.2.0` (+mlx-metal, skrub) to projects/12 — currently unusable without the license token (see OPEN_QUESTIONS).

## Remaining for the owner

1. Review the commits (done by owner 2026-11-19: `390c141` queue implementation, `e9a770b` collaboration records, `a503643` deploy log).
2. ~~Redeploy~~ — done 2026-11-19: `e9a770b` is live on alejandromerida.dev; smoke suite green, the 02/08/11 metrics error box verified gone in a real browser.
3. Decide the open questions — three blocked items end-to-end (04-NLP cascade per-row persistence, 12-TabPFN license acceptance, 06-routing ALNS-vs-unhinted interval which needs a new solve) and one partial block (02-M5 reconciled-baseline row). OPEN_QUESTIONS.md files: `collaboration/designs/20261117-04-nlp-review-fixes/`, `collaboration/designs/20261117-12-tabular-review-fixes/`, `collaboration/designs/20261117-06-routing-review-fixes/` (interval), `collaboration/designs/20261117-02-m5-review-fixes/` (reconciled row).
4. Decide whether to surface the PyVRP comparator in the 06 README/story (new-solver scope).
5. Known pre-existing oddity noticed while working: the provenance stamp convention replaces `_meta` results blocks with provenance (e.g. project 10's committed metrics.json no longer carries the `_meta.ci/cuped` detail the README references) — worth a separate look.
6. Pre-queue uncommitted visualization work was committed and deployed together with the queue on 2026-11-19 (pareto label fix and diagram fit-by-default landed on top of it before the push).
