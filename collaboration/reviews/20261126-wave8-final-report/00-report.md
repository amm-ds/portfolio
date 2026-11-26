# Wave 8 final report — published articles, projects 02–13

Date: 2026-11-26 · Reviewer: Claude (design/review lane) · Branch `wave8-articles-truthfulness-2026-11-25`, HEAD `ebb889cf`, working tree clean at start.

Scope: graded review of the published case-study articles (`projects/NN-*/story.yaml`) for projects 02–13, with projects 01 and 15 read as reference only (not graded). No project, app or docs file was edited. No git mutation, training, refit, experiment, hosted or paid call, and no long pytest/npm suite was run. Earlier reviews (`opus-round3/`, `20261126-*`) were read as background; every grade below rests on evidence re-checked in this pass.

## Gates re-run this pass (cheap, read-only)

| Gate | Exit | Output |
|---|---|---|
| `scripts/lint_story_language.py` | 0 | 14 stories, 0 errors, 0 warnings |
| `scripts/check_headline_numbers.py` | 0 | 13 claims, 0 findings (04 registered as "uncovered") |
| `scripts/check_docs.py` | 0 | OK |
| `scripts/check_demo_contract.py` | 0 | forecast-workbench, churn-sandbox OK |
| `scripts/check_figure_axes.py` | 0 | 158 figures, 3 over-wide window warnings |
| `scripts/check_figure_budget.py` | 0 | 1 figure over 500 KiB warn line (`03/.../telemetry_flags.json`, 519 KiB) |
| `scripts/check_short_copy.py --check` | 0 | 42 surfaces single-sourced |
| `scripts/gen_static_registry.py --check` | 0 | current |
| `scripts/gen_story_short.py --check` | 0 | current |
| `scripts/gen_route_manifest.py --check` | 0 | 28 routes current |

Full pytest (97.14% coverage), npm test/lint/build and mkdocs strict were recorded as exit 0 at this HEAD in `collaboration/reviews/20261126-wave8-commit-handoff/00-commit-handoff.md:31-47`; not re-run (instruction).

Structural checks run this pass: every figure id named in a story's `figures:` list has a committed JSON under `reports*/figures/`, a caption in `figure_captions`, and a generator reference under `src/` (06 `route_map_C101` is built by an f-string at `06/src/routing_optimization/evaluate.py:704`). Every ` ```diagram <id>` fence in 02–13 resolves to a spec under `apps/showcase-web/src/diagrams/`.

---

## 1. Portfolio-level verdict

**Verdict: the twelve articles are truthful to their committed artifacts and fit to publish. No project is on HOLD. Ship with the notes below; two cross-project wording items (13 "champion", 02 demo blend) should be fixed in the next small pass.**

### What the twelve projects together show

- **A consistent evaluation discipline.** Every project fixes a floor before the model (seasonal naive in 02/12, random in 03, majority/random in 04, contact-everyone in 05, randomized in 06, persistence in 07, random targeting in 10, pandas in 11). Every one selects on validation or training-side data and scores a frozen window once. 07 serves the validation winner although XGBoost wins on test (`07/story.yaml:181-184,349-353`). 12 serves a validation-tied MLP and says so (`12/story.yaml:366-371`).
- **Uncertainty is stated where it exists and its absence is admitted where it does not.** Paired bootstraps in 03, 05, 06, 07, 10 and 12. Explicit "no interval" statements in 02 (`02/story.yaml:207`) and 04 (`04/story.yaml:238-240`).
- **Negative results are published.** 02 spike capture and Huber challengers (`02/story.yaml:161-163`), 03 fusion/calibration (`03/story.yaml:131`), 04 HPO inconclusive, 06 restarts never pay, 10 CUPED null, 12 dropout-off beats the shipped config.
- **The range is broad and real:** forecasting, anomaly detection, NLP plus an LLM cascade, cost-sensitive classification, combinatorial optimization, a geospatial data pipeline, LLM serving, agentic workflows, causal uplift, an engine benchmark, the tabular ML lifecycle, and model serving/containers.
- **The headline results are honest and moderate.** No article overclaims. Several results are deliberately framed as ties or small effects (02 blend vs best single, 04 cascade +0.001, 10 Qini, 12 MLP vs LightGBM).

### Cross-project inconsistencies found

1. **12 vs 13, "champion".** 12 says the MLP is served "without a champion label" (`12/story.yaml:369-371`; the artifact itself says "not a proven champion", `12/reports/metrics.json:38`). 13 calls the same model "the champion tabular MLP" nine times, starting in the headline (`13/story.yaml:2,6,20,53,60,116,264,359,374`). The numbers agree: both report 25.4316 test MAE (`13/reports/metrics.json:219` = `12/reports/metrics.json:17`). The label contradicts 12 and the owner decision recorded in 12's artifact. **Fix: replace "champion" with "served" or "validation-selected" in 13's copy.**
2. **02 demo vs article.** The demo and the sample-series figure use an earlier blend, 0.6161 WRMSSE with weights 0.60/0.10/0.30 (`02/reports_m5_full/demo_payload.json`, `groups.test_pooled.convex_ensemble`; `n_selection: 2` at `:20245`). The article headline uses the current champion, 0.6211 with weights 0.95/0.00/0.05 (`02/reports_m5_full/metrics.json:608`). Both are disclosed in the article (`02/story.yaml:173,241`), in `demo.yaml:15-17` and in the demo UI (`ForecastWorkbench.tsx:31-35,307-317,424-430`). Two residual issues:
   - On the same test window the earlier blend scores *better* (lower) than the champion. The article never says why it was replaced. Only the demo's "experiment" block gives the reason (2 versus 9 selection origins). A reader can take this for a regression.
   - The demo's per-member pooled curves also come from the earlier fit and do not match the article: `lgbm_pool_storecat` 0.6575 in the payload vs 0.6225 in `metrics.json`; `lgbm_pool_dept` 0.6313 vs 0.6459. The demo labels them only as "earlier-run pooled WRMSSE" in one KPI subtitle (`ForecastWorkbench.tsx:302`).
   **Fix (copy only): one sentence in `02/story.yaml:173` saying the champion was re-selected on 9 origins rather than 2. Optionally, label all demo member numbers as earlier-run.**
3. **Electricity assumptions on the same host.** 08 declares 100 W (`08/params.yaml:51`), 13 declares 65 W (`13/params.yaml:59`). Both use $0.30/kWh, and both appear to run on the same M4 Max-class laptop (04, 08, 11, 12 and 13 all describe a 16-core arm64 Apple host). Each article labels its wattage as a declared assumption, so this is not false, but the cost lines are not comparable across projects. Note only.
4. **Conclusions structure.** Only 03 and 12 follow project 01's order (Taught → Limits → Exact numbers → Protocol). The other ten graded articles (02, 04–11, 13) keep a `## Results summary` heading and put Limits after Protocol (e.g. `02/story.yaml:171,197,205`; `04/story.yaml:298,414,451`). This is a consistency issue, not a truth issue.
5. **Consistent across projects (verified):**
   - 12→13 test MAE 25.4316, validation MAE 34.217 and `atemp` pruning (r 0.9873 in `13/reports/metrics.json` `selection`; "r = 0.99" in 12).
   - 01→09 corpus of 3,589 chunks (`01/DESIGN.md:239`; `09/story.yaml:78`).
   - 07/11 NYC TLC snapshot family and "N/A" borough handling.

### Remaining style debt (non-blocking)

- Ten verbless section-intro lines of the form "Next, the X ([Objectives →](#sec-objectives))." remain at 03:22, 05:19, 06:19, 07:52, 08:59, 09:32, 10:49, 11:19, 12:28 and 13:31. They were optional in the fix list.
- One "; next, we …" splice remains at `03/story.yaml:115`. The round-3 grep for `; next, the` could not catch it.

---

## 2. Summary table

Scores are 0–10. Overall is the rounded mean of the five axes, adjusted by at most ±0.3 for ship-relevant notes.

| # | Project | Content | Code | Perf. | Results | Present. | Overall | Ship status |
|---|---|---|---|---|---|---|---|---|
| 02 | Demand forecasting (M5) | 8 | 8 | 7 | 9 | 7 | 7.8 | SHIP WITH NOTES |
| 03 | Anomaly detection (NAB) | 7 | 8 | 6 | 9 | 8 | 7.6 | SHIP WITH NOTES |
| 04 | NLP classification (AG News) | 7 | 8 | 8 | 9 | 8 | 8.0 | SHIP WITH NOTES |
| 05 | Churn pipeline (Telco) | 8 | 8 | 7 | 9 | 8 | 8.0 | SHIP |
| 06 | Routing (Solomon VRPTW) | 8 | 9 | 6 | 9 | 8 | 8.0 | SHIP |
| 07 | Open-data mobility (NYC TLC) | 9 | 8 | 7 | 9 | 8 | 8.2 | SHIP |
| 08 | LLM inference serving | 7 | 7 | 6 | 9 | 7 | 7.2 | SHIP WITH NOTES |
| 09 | Agentic workflows | 7 | 8 | 7 | 8 | 8 | 7.6 | SHIP WITH NOTES |
| 10 | Uplift experimentation (Hillstrom) | 7 | 7 | 6 | 7 | 8 | 7.0 | SHIP WITH NOTES |
| 11 | DataFrame engines benchmark | 9 | 9 | 8 | 9 | 8 | 8.6 | SHIP |
| 12 | Tabular ML lifecycle (bike sharing) | 8 | 7 | 7 | 9 | 8 | 7.8 | SHIP WITH NOTES |
| 13 | Model serving (FastAPI/ONNX) | 7 | 9 | 8 | 9 | 8 | 8.2 | SHIP WITH NOTES |

No HOLD.

---

## 3. Per-project grades and evidence

Paths are relative to `projects/<NN>-*/` unless they start at the repo root.

### 02 — Demand forecasting (M5 full panel)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 8 | Clear, reader-facing, limits stated (no bootstrap CI on the headline, floor wins zero days, test-window reuse disclosed). Conclusions keep `## Results summary` and put Limits after Protocol. The article never explains why the better-scoring earlier blend (0.6161) was replaced. | `story.yaml:2-4,31,171,197,205-210,173` |
| Code | 8 | Selection code is excerpted and linked. Figure generator and tests exist (`test_m5_full.py`, `test_m5_full_payload.py`, `test_readme_numbers.py`). The demo payload cannot be regenerated from current metrics without a catalog refit: the guard fails by design (`OPEN_QUESTIONS.md`). | `src/demand_forecasting/m5_full_figures.py`; `tests/`; `collaboration/designs/20261126-wave8-round3-article-fixes/OPEN_QUESTIONS.md:9-13` |
| Performance | 7 | −30.4% official WRMSSE against seasonal naive on the full 30,490-series panel is a solid internal result. The ensemble edge over the best single fit (0.0008) is about 1.3× the noise band, and the floor still wins zero-sale days (66.6% vs 57.2%). No external-leaderboard claim is made. | `reports_m5_full/metrics.json:245,277,472,608,626` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 7 | Four figures from a committed generator. Titles and captions match the data (sample-series origin is now 2016-05-22). The demo shows earlier-run member numbers that differ from the article (storecat 0.6575 vs 0.6225), labelled only in one subtitle. | `reports_m5_full/figures/*.json` titles; `ForecastWorkbench.tsx:302,308-317,424-430` |

Spot checks:
- Champion 0.6211 → `metrics.json:608` (0.62105) — **verified**.
- Floor 0.8929, −30.4% → `metrics.json` `test.seasonal_naive.official_wrmsse` 0.89290 (1 − 0.62105/0.89290 = 30.4%) — **verified**.
- Zero-day 57.2% vs 66.6% → `metrics.json:626,472` — **verified**.
- Per-level total 0.314 vs 0.560 (−43.9%), item-store gap 0.341 → `metrics.json:611` and `test.seasonal_naive.per_level_wrmsse` — **verified**.
- Best single 0.6219, WAPE 0.7617, bias +0.0177 → `test.lgbm_pool_store` — **verified**.
- Routed challenger 0.6235, Huber 0.8683 vs 0.7409 → `metrics.json:247`; `erratic_challenger.json:27-28` — **verified**.
- Demo hero 0.6161 vs 0.8929 → `demo_payload.json` `groups.test_pooled` — **verified**, as an earlier blend.

Ship: **SHIP WITH NOTES.** Add one sentence on why the champion replaced the earlier 0.6161 blend (2 vs 9 selection origins). Optionally move Limits ahead of Exact numbers.

### 03 — Anomaly detection (NAB)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 7 | Accurate and limits-forward ("roughly half its pages outside incidents"; NAB score not reported). Very dense with numbers. One "; next, we" splice, one verbless intro, and a citation aside in table prose ("per Lyu 2026, preprint: … single unreplicated source"). Conclusions order matches 01. | `story.yaml:22,115,155-160,205-206,248-253` |
| Code | 8 | Rank-ensemble code excerpted from `nab_sweep.py`. Generators `nab_sweep.py`, `range_pr.py`, `nab_tune.py` and matching tests `test_nab*.py`, `test_range_pr.py`. | `src/anomaly_detection/`; `tests/` |
| Performance | 6 | Range-PR area 0.804 against a 0.228 no-skill band is clearly above chance. But the best budgeted range precision is 0.553, tuning does not clear its adoption margin, and no official NAB score is reported. This is an alert-budget dial, not a production detector, and the article says so. | `reports/nab_metrics.json:750,787`; `reports/nab_sweep.json:1056` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | 11 figures with captions that match the data. `telemetry_flags.json` is over the 519 KiB warn line. Unreferenced `score_distribution.json` is left in `reports/figures`. | `check_figure_budget` output; `reports/figures/` |

Spot checks:
- IF rolling+residual 1,609 → 80 pages, range-F1 0.157 → 0.315 → `nab_sweep.json` grid `isolation_forest+rolling_residual` — **verified**.
- Ensemble rolling 1,157 → 35, recall 0.604, F1 0.533, precision 0.553 → `nab_sweep.json:1056` — **verified**.
- Range-PR 0.804 vs 0.228 [0.081, 0.401]; precision@2% 0.527, CI [0.230, 0.811] → `nab_metrics.json:750,787` and `no_skill` — **verified**.
- 16/17 windows, PR-AUC 0.527 → `nab_metrics.json` `overall` — **verified**.

Ship: **SHIP WITH NOTES.** Rewrite `story.yaml:115` and `:22` as full sentences. Move the Lyu citation aside out of the table lead-in.

### 04 — NLP classification (AG News + LLM cascade)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 7 | Accurate. It states that the cascade gain is unproven and that HPO is inconclusive. It over-explains basics in reader copy ("CPU is the computer's main processor", MB/p50 glossary in the table lead-in). Results summary and Limits come after Protocol. | `story.yaml:17,240,268-270,401-406,298,451` |
| Code | 8 | Calibration excerpt is real. Tests cover the fresh holdout, cascade, scale ladder and latency. Per-row cascade decisions are not persisted, so no paired CI is possible, and the project is registered "uncovered" in the headline gate. | `tests/test_llm_cascade.py`, `test_fresh_holdout.py`; `scripts/check_headline_numbers.py` KNOWN_DRIFT |
| Performance | 8 | 0.953 fresh macro-F1 for DistilBERT on AG News is near the published fine-tuned-transformer range (about 0.95). The ladder is monotone and data scale is shown to drive the gain. The cascade adds nothing measurable. | `reports/fresh_holdout.json:53`; `reports/metrics.json:27` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | Seven figures with matching captions. The `routing.ts` 0.9061 fixture is recorded as test-only. | `story.yaml:502-520` |

Spot checks:
- Fresh 0.9529 → 0.9539 with 22 reviews → `llm_cascade.json:32-36` — **verified**.
- $0.023671 and 96.933 s → `llm_cascade.json:42-43` — **verified**.
- Test 0.9460 full-120k; TF-IDF 0.8714 → `metrics.json:27` and `baseline_tfidf_logreg` — **verified**.
- HPO delta +0.0073 → `selection.json:24-26` — **verified**.
- Keyword router 0.9061 → `fresh_holdout.json:107` — **verified**.

Ship: **SHIP WITH NOTES.** Trim the glossary-style asides. Align the conclusions order with 01.

### 05 — Churn pipeline (IBM Telco)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 8 | Clear cost framing. It separates the raw-model fairness slices from the served policy and states that the bootstrap omits selection variance. It cites `data/operating_policy.json`, which is gitignored; the committed equivalent is `reports/models/serving/meta.json` `threshold_selection`. | `story.yaml:191,329,236-246`; `.gitignore:15` |
| Code | 8 | `business_cost`/`cost_curve` excerpt; tests for the demo payload, evaluation and serving; the sensitivity CLI writes a committed artifact. The raw OOF cost of $2,440 appears only in `report.html`/`decision_curve.json`, not in `metrics.json`. | `reports/sensitivity.json`; `reports/models/serving/meta.json` |
| Performance | 7 | ROC-AUC 0.83–0.84 is typical for Telco. A 41.9% cost cut against contact-everyone with a CI that excludes zero is a real decision gain under a stated 1:5 cost ratio. | `reports/metrics.json:37-46` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | Seven figures. The demo states what it shows and is consistent with the article ($601 / $1,035 / [−508, −353]). Its threshold grid is 0.02-spaced, so the served 0.175 is not a grid point. | `ChurnSandbox.tsx:629-680`; `reports/demo_payload.json` |

Spot checks:
- $601 vs $1,035 → `metrics.json:46,29` — **verified**.
- CI [−508, −353] → `sensitivity.json:34-35` — **verified**.
- ECE 0.028 → 0.016; AUC 0.8387 → 0.8317 → `metrics.json` `selected_model*` — **verified**.
- Sensitivity at FN = 3 and FN = 8: $514 / $718, thresholds 0.250 / 0.150 → `sensitivity.json` `fn3`, `fn8` — **verified**.

Ship: **SHIP.** Optional: point the provenance at the committed `reports/models/serving/meta.json`.

### 06 — Routing optimization (Solomon VRPTW)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 8 | Distance is always shown beside the fleet delta. It states that best-known is not optimal, that hinted CP-SAT is not independent, and that runtimes come from a shared machine. One verbless intro. | `story.yaml:19,147-153,311-321` |
| Code | 9 | ALNS excerpt; validator before scoring; `test_committed_solutions.py`; seeded and deterministic; the CI on the mean gap is in metrics. | `tests/test_committed_solutions.py`; `reports/metrics.json:3899-3934` |
| Performance | 6 | 4.23% distance gap at about 1 s per instance with +3.73 vehicles against vehicle-first best-knowns. That is far from state-of-the-art VRPTW solvers that reach best-known fleets. Honest, but modest. | `reports/metrics.json` `summary.alns` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | Seven figures. The C101 caption matches `results.md:78` (860.21, 11 routes, 3.77%). | `reports/results.md:73-80` |

Spot checks:
- Mean gap 4.23%, CI [3.22, 5.28] → `metrics.json:3899-3934` — **verified**.
- +3.73 / +3.66 vehicles; 316.95% randomized; 71.64% nearest neighbour; 13.63% tuned 2-opt → `metrics.json` `summary` — **verified**.
- Hinted CP-SAT 12.0 s vs ALNS 1.15 s; unhinted UNKNOWN on all instances → `summary.ortools_cp`, `unhinted_cp_sat` — **verified**.

Ship: **SHIP.**

### 07 — Open-data mobility (NYC TLC)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 9 | The best-written of the set on selection discipline (serves the validation winner, not the test leader). Limits are explicit: sparse boroughs, the no-borough bucket, weather as association only, and a test-derived conformal adjustment. | `story.yaml:175-189,349-353,431-452` |
| Code | 8 | Serving-selection excerpt from `serving.py`; tests for conformal, drift, transfer and serving; paired intervals in metrics. A rerun needs the 1.5 GB pinned download. | `tests/`; `reports/metrics.json` `paired_intervals` |
| Performance | 7 | −28.3% MAE against persistence (MASE 0.763) is solid. XGBoost is 4.1% better on test but not served. Persistence beats every GBM in three sparse boroughs. | `reports/metrics.json:76-100` |
| Results | 9 | Checks below verified. Coverage 90.8% is in committed figure data, not in `metrics.json`. | see below |
| Presentation | 8 | Nine figures with matching captions. | `story.yaml:5-28` |

Spot checks:
- 4.676 vs 6.517 MAE, −28.3% → `metrics.json:88,100` — **verified**.
- XGBoost 4.487 (−31.2%) → `metrics.json:94` — **verified**.
- p90 coverage 90.8% overall, 84.7% N/A → `reports/figures/p90_calibration.json` (0.9079, 0.8473) — **verified** (figure data).
- January 2025 drift coverage 87.4% → `reports/drift/2025-01.json` `p90_coverage` 0.8738 — **verified**.
- Green retrain 0.180 vs 0.212 → `reports/green_transfer.json` — **verified**.

Ship: **SHIP.**

### 08 — LLM inference serving

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 7 | Honest about the saturated quality check, packaging confounds and single-host limits. Quantization labels are internally inconsistent: training calls the MLX 31B "unrecorded quantization" (`:167`), while the engine panel and its caption call the MLX arm "4-bit" (`:14,260,296`). The two are different tags (`gemma4:31b` vs `gemma4:31b-mlx`), and the 4-bit label rests only on a `params.yaml` comment. "Five setups" does not map cleanly onto seven model tags. | `story.yaml:14,165-170,260,296`; `params.yaml:36-44` |
| Code | 7 | Benchmark excerpt; raw `data/bench_run.json` committed; percentiles recomputed offline; tests for bench math and figures. Re-measurement needs the same hardware, and the repeat file is correctly left uncommitted. | `data/bench_run.json`; `tests/test_bench_math.py` |
| Performance | 6 | Clean measurements (760 requests, 0 failures). The MoE wins on speed, but there is no quality evaluation beyond a saturated format and keyword check. | `reports/metrics.json` `cells` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 7 | The engine-panel figure subtitle says "same gemma4:31b weights" while the caption says quantization differs. The diagram fence at `:316` is indented 6 spaces; it renders because `FENCE_RE` allows leading whitespace (`apps/showcase-web/src/lib/markdown.tsx:188`), but the source is irregular. | `reports/figures/engine_panel.json` title; `story.yaml:316` |

Spot checks:
- p95 0.81 s, p50 0.63 s, 67.73 tok/s at c=1 → `metrics.json:22` (cell 0) — **verified**.
- 7.80 s at c=8 → cell `qwen3.6` c=8 p95 7.7998 — **verified**.
- 7× the 32B → 67.73 / 9.56 → `metrics.json:217` — **verified**.
- 760 requests = 19 cells × 40 → `metrics.json` `cells` — **verified**.
- $0.12 per 1M tokens → 1e6 / 67.73 / 3600 × 0.1 kW × $0.30 = $0.123 — **verified**.

Ship: **SHIP WITH NOTES.** Reconcile the "unrecorded" vs "4-bit" wording for the two gemma tags. Fix the engine-panel subtitle ("same model family", not "same weights"). De-indent the fence at `:316`.

### 09 — Agentic workflows

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 7 | Accurate and limits-forward (supervised pilot only, n = 19, local latency failures). Two problems for reader-facing copy: it links readers into a review-process folder (`collaboration/reviews/20261118-live-confirmation/comparison.md`), and it uses process jargon ("legacy grader", "live grader", "h19 … calculator guard tripped") in the short version. | `story.yaml:2-4,204,253-254` |
| Code | 8 | HITL resume excerpt; deterministic graders; tests for HITL, evals and suite budget; recorded runs committed. | `tests/test_hitl.py`, `test_evals.py`; `data/run_records.json` |
| Performance | 7 | 15/15 and 13/13 with zero unplanned calls is clean, but the suites are small (Wilson lower bound 0.77–0.80). The legacy refusal is 5/6, and local latency misses 7/9. | `reports/metrics.json` `detail.pass_rate_intervals` |
| Results | 8 | Legacy checks verified in `reports/metrics.json`. The live 6/6 and 19/19 are verified only in a review folder, not in the project's `reports/`. | see below |
| Presentation | 8 | Four figures. Captions match: median 18.2 s, p95 31.1 s, t05 31.6 s. | `story.yaml:6-18` |

Spot checks:
- 15/15; p95 31.1 s; median 18.2 s; $0.0088 per task → `metrics.json:6` and per-task latencies (median 18.227) — **verified**.
- Held-out 13/13, 5/6, 18/19, 12/19; 22 calls → `metrics.json` `detail.heldout` — **verified**.
- Live 6/6 refusals and 19/19 budgets → `collaboration/reviews/20261118-live-confirmation/live-grading/metrics.json` — **verified**, but evidence sits outside `projects/09/reports/`.

Ship: **SHIP WITH NOTES.** Move the live-confirmation evidence (or a copy) under `projects/09-agentic-workflows/reports/` and link that instead of a review folder. Simplify the short version.

### 10 — Uplift experimentation (Hillstrom)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 7 | Truthful and carefully bounded (mail-everyone wins at $0.01; channel choice unproven; planning money kept apart from observed DR/IPW). Very dense. The two Qini intervals for the same score, [0.77, 24.39] and [−0.47, 24.21], are disclosed but confusing next to "neither ranking is established". | `story.yaml:236-244,274-276` |
| Code | 7 | The cross-fitting excerpt is real and tests cover CUPED, Qini, policy value and power. The two-arm paired intervals ([+$718, +$4,767], Qini [0.77, 24.39], [−8.18, 9.52], [−$13,125, −$5,808]) exist only in the rendered `reports/report.html`, not in `metrics.json`, and the headline gate checks only the point. `reports/demo_payload.json` exists with no demo. | `reports/report.html`; `reports/metrics.json:658`; `scripts/check_headline_numbers.py` `_m10` |
| Performance | 6 | The targeted-vs-random gain at a 25% budget is significant. The model-vs-response ranking is not established, the per-arm AUUCs span zero, the predicted spread is 2× too wide, and mail-everyone wins at the real send cost. | `story.yaml:296-312` |
| Results | 7 | Points verified in `metrics.json`; CIs verified only against `report.html`. | see below |
| Presentation | 8 | Nine figures with matching captions. `qini_per_arm.json` x-axis window is 4.4× the data span (axes warning). | `check_figure_axes` output |

Spot checks:
- +$2,812 vs random; $6,838 at budget; random $4,026 → `metrics.json:658` (`t_learner`) — **verified**.
- Mail-everyone $16,103 → `metrics.json` `profit_full` — **verified**.
- Qini 12.03 → `t_learner.qini_coefficient` 12.025 — **verified**.
- CI [+$718, +$4,767] → `report.html` only — **verified (HTML), not verified (machine-readable)**.
- DR gain +$6,990 → `metrics.json:370` — **verified**.

Ship: **SHIP WITH NOTES.** Persist the two-arm paired intervals into `metrics.json` and extend the headline gate to cover them. Remove or wire up the orphan `demo_payload.json`. Add one sentence reconciling the two Qini interval protocols.

### 11 — DataFrame engines benchmark

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 9 | Clear and correct. Parity comes before speed, and sqlite's load cost and cache limits are explained. One navigation quirk: the EDA section says the next figure is in Evaluation, but Training comes next. | `story.yaml:123-124` |
| Code | 9 | Determinism, engine and figure tests; canonical-result contract; per-task cells committed; versions in metadata. | `tests/test_determinism.py`, `test_figures.py`; `reports/evaluation_metadata.json` |
| Performance | 8 | Well-executed benchmark: 39/39 cells pass parity, scaling slopes are committed, and a real data-loss bug (1,658 trips) was caught. | `reports/metrics.json:2245` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | Five figures with matching captions; tables mirror metrics. | `story.yaml:405-424` |

Spot checks:
- Polars ×19.2 and DuckDB ×14.9 → `metrics.json:737,729` (19.157 / 14.886) — **verified**.
- Totals 0.16 / 0.22 / 2.99 / 40.55 s → `summary.by_engine` — **verified**.
- 1,658 N/A trips → `metrics.json:2245` — **verified**.
- Versions pandas 2.3.3, Polars 2.0.0, DuckDB 2.0.0, pyarrow 26 → `evaluation_metadata.json` — **verified**.

Ship: **SHIP.**

### 12 — Tabular ML lifecycle (UCI bike sharing)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 8 | Accurate. It names the MLP/LightGBM tie, the serial-dependence sensitivity, the positional-lag gap, and that the ablation does not select. Conclusions order matches 01. | `story.yaml:340-350,364-371` |
| Code | 7 | Training loop excerpt; seeded and deterministic; tests for stages, figures and models. A known defect stays in the committed run: the correlated-pair rule drops the higher-MI member (`atemp`), and the article says correcting it needs a fresh run. Lags are positional across the 36-hour gap. | `story.yaml:148-150,318-320`; `reports/metrics.json` |
| Performance | 7 | 25.4 vs 83.2 MAE (−57.8, CI excludes zero under hourly, day and week blocks) is a strong gain over the floor. The MLP is only tied with LightGBM (val −0.18 [−1.71, +1.21]). | `reports/metrics.json:12,17,32,38` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | 11 figures with matching captions. `bootstrap_ci` figure data carries the exact bounds. | `reports/figures/bootstrap_ci.json` |

Spot checks:
- MLP 25.43, LightGBM 25.37, floor 83.20 → `metrics.json:17,12,32` — **verified**.
- Gain CI [52.49, 63.07], week block [38.82, 73.41] → `figures/bootstrap_ci.json`; `results.md:17` — **verified**.
- Validation tie −0.18 [−1.71, +1.21] → `metrics.json` `validation_tie_interval` — **verified**.
- Validation MAE 34.22; dropout-off 32.13 → `train_runs.json` — **verified**.

Ship: **SHIP WITH NOTES.** The disclosed pruning defect is the next-round fix (roadmap gate at `story.yaml:424-425`). The process phrase "per owner decision 8" in `reports/metrics.json:38` leaks review language into a public artifact; reword it at the next regeneration.

### 13 — Model serving (FastAPI, ONNX, Docker)

| Axis | Grade | Reason | Evidence |
|---|---|---|---|
| Content | 7 | Clear, with host limits stated, the slim-image answer measured, and wattage declared. It calls the model "champion" nine times, which contradicts 12 (see cross-project item 1). | `story.yaml:2,6,20,53,60,116,264,359,374` |
| Code | 9 | Exact reproduction gate (abs diff 0.0) and parity gate enforced before benchmark; tests for parity, service, Dockerfile and bench math; Docker evidence committed. | `reports/metrics.json:210,219`; `tests/test_parity.py`, `test_dockerfile.py` |
| Performance | 8 | 1.6 ms p50, a knee near 950 req/s, zero errors over 4,320 requests per backend, and a 22.2× smaller ONNX-only image. Strong for a single-worker laptop service. | `reports/metrics.json` `serving`, `docker`; `reports/docker_slim.json` |
| Results | 9 | All checks below verified. | see below |
| Presentation | 8 | Four figures with matching captions. The exact table matches metrics (ONNX c64 throughput 715, p95 209.8 ms). | `story.yaml:283-292` |

Spot checks:
- p50 1.6 ms; p95 2.0 / 1.9 ms; p99 2.2 ms → `serving.native.concurrency.c1` 0.00163 / 0.00199 and `onnx.c1` 0.00158 / 0.00187 / 0.00220 — **verified**.
- Knee 933 / 970 req/s → `native.c4`, `onnx.c4` — **verified**.
- Image 6,466 MB vs slim 291 MB (22.2×) → `metrics.json:187`; `docker_slim.json` — **verified**.
- Parity 7.15e-07; reproduction 25.43163 → `metrics.json:210,219` — **verified**.
- c64 throughput +13.8% for ONNX (714.9 / 628.3) — **verified**.

Ship: **SHIP WITH NOTES.** Replace "champion" with "served" or "validation-selected" throughout `story.yaml` (and the README and `portfolio.yaml`, which also use it).

---

## 4. Reference projects (not graded)

- **01 RAG agent.** Conclusions use the gold order (Taught → Limits → Exact numbers → Measured alternatives → Protocol; `01/story.yaml:197-254`), with no `## Results summary`. Headline numbers are covered by the gate (F1 0.909 and recall@5 0.946 via `_m01`). Used as the structural reference above.
- **15 Dynamic pricing RL.** Out of scope for Wave 8. The headline is a candid negative result (PPO trails static B1 by −1.86%, CI [−0.0114, −0.0080]). It still has a verbless intro (`15/story.yaml:34`) and a "; next, the" splice (`:117`).

## 5. HOLD blockers

None.

## 6. Push readiness — main and production

**YES WITH NOTES.**

Why yes:
- Every cheap gate exits 0 at `ebb889cf`, and the full gate record (pytest 97.14%, npm test/lint/build, mkdocs strict) is 0 at this HEAD.
- Every headline number spot-checked in 02–13 matches a committed artifact.
- No article makes a claim its artifacts contradict.
- Both demos state what they show, and the 02 demo's earlier-blend payload is labelled.

Notes to carry (none blocking):
1. 13: drop the "champion" label so it matches 12 and its owner decision.
2. 02: one sentence on why the 0.6161 blend was superseded; optionally label the demo's earlier-run member numbers.
3. 10: persist the two-arm paired CIs into `metrics.json` and gate them.
4. 09: host the live-confirmation evidence under the project's `reports/`, not a review folder.
5. 08: reconcile the gemma quantization labels and the engine-panel subtitle.
6. Style: ten verbless intros and `03/story.yaml:115`; conclusions order in 10 of 12 articles.

Not verified in this pass: the full pytest/npm/mkdocs suites (taken from the recorded gate table), production deploy behaviour, and rendered-page appearance in a browser.
