# Post-deploy grades — projects 01 to 15

Date: 2026-11-26 · Reviewer: Claude (review lane) · Repo HEAD `acf6f9f7` (= `origin/main`), working tree clean apart from the untracked `collaboration/reviews/20261126-wave8-prepush-review/`.

Scope: a read-only, portfolio-wide pass over the 14 published projects (01–13 and 15; there is no project 14). No repo file was edited except this one. There were no git mutations, and no training, refit, benchmark, experiment, hosted or paid call. Long pytest/npm suites were not run.

Paths are relative to `projects/<NN>-*/` unless they start at the repo root.

## 0. Headline finding: production is not serving Wave 8

The app at `https://alejandromerida.dev` is still on **`c05accd0`**, two commits behind `main`:

- `GET https://alejandromerida.dev/health` → `"sha":"c05accd096ee2209bc7bb8362aa15bf3ec171fc5"` (read 2026-11-26 14:56 UTC). The page `<meta name="build-sha">` gives the same sha.
- The live 13 story (`/projects/13-model-serving/story`) and the rendered page in the browser pane both contain **"champion" 11 times**. `c05accd0:projects/13-model-serving/story.yaml` also has 11, and HEAD has 0. The live `<meta name="description">` still reads "Experiment 12's champion MLP … re-derived".
- The live 02 story does not have the new `acf6f9f7` disclosure ("earlier blend" appears 0 times live and 1 time at HEAD).
- The mkdocs site **is** current. `https://amm-ds.github.io/portfolio/projects/13-model-serving/` returns 200 and reads "served MLP".

So the `ebb889cf` and `acf6f9f7` truthfulness fixes are on GitHub Pages but not on the app. **The app deploy has to be re-run and checked against `/health` before Wave 8 counts as deployed.** The grades below are for the committed HEAD. Where the live app differs, the note says so.

## 1. Gates re-run in this pass (cheap, read-only)

| Gate | Exit | Output |
|---|---|---|
| `scripts/lint_story_language.py` | 0 | 14 stories, 0 errors, 0 warnings |
| `scripts/check_headline_numbers.py` | 0 | 13 claims, 0 findings (04 registered "uncovered") |
| `scripts/check_docs.py` | 0 | OK |
| `scripts/check_demo_contract.py` | 0 | forecast-workbench, churn-sandbox OK |
| `scripts/check_figure_axes.py` | 0 | 158 figures; 3 over-wide warnings (`01 retrieval_ladder` y 15.1× and y2 4.5×, `10 qini_per_arm` x 4.4×) |
| `scripts/check_figure_budget.py` | 0 | 1 warning: `03/reports/figures/telemetry_flags.json` 519 KiB |
| `scripts/check_short_copy.py --check` | 0 | 42 surfaces single-sourced |
| `scripts/gen_static_registry.py --check` | 0 | current |
| `scripts/gen_story_short.py --check` | 0 | current |
| `scripts/gen_route_manifest.py --check` | 0 | 28 routes current |

Structural checks run in this pass:
- Every figure id in every story's `figures:` lists has a committed JSON under `reports*/figures/` and a `figure_captions` entry.
- Every figure id is referenced by a generator under `src/`. The one exception is 06 `route_map_C101`, which is built by an f-string.
- Diagram fences: 01's five ids all resolve under `apps/showcase-web/src/diagrams/`. **None of 15's five ids resolves** (see 15). No gate checks this.

## 2. Grade table

Axes are 0–10. Overall is the mean of the four, rounded to one decimal.
Status rule:
- **STRONG**: overall ≥ 8.5 and no axis below 8.
- **NEEDS WORK**: overall < 7.5, or any axis ≤ 6.
- **SOLID**: everything else.

| # | Project | Contents | Results | Technologies | Visualizations | Overall | Status |
|---|---|---|---|---|---|---|---|
| 01 | RAG agent | 8 | 9 | 8 | 8 | 8.3 | SOLID |
| 02 | Demand forecasting (M5) | 8 | 9 | 8 | 7 | 8.0 | SOLID |
| 03 | Anomaly detection (NAB) | 7 | 9 | 8 | 6 | 7.5 | NEEDS WORK |
| 04 | NLP classification + cascade | 7 | 9 | 8 | 8 | 8.0 | SOLID |
| 05 | Churn pipeline | 8 | 9 | 8 | 8 | 8.3 | SOLID |
| 06 | Routing (VRPTW) | 8 | 9 | 9 | 8 | 8.5 | STRONG |
| 07 | Open-data mobility | 8 | 9 | 8 | 8 | 8.3 | SOLID |
| 08 | LLM inference serving | 6 | 9 | 6 | 6 | 6.8 | NEEDS WORK |
| 09 | Agentic workflows | 7 | 8 | 8 | 8 | 7.8 | SOLID |
| 10 | Uplift experimentation | 7 | 7 | 7 | 7 | 7.0 | NEEDS WORK |
| 11 | DataFrame engines benchmark | 9 | 9 | 9 | 8 | 8.8 | STRONG |
| 12 | Tabular ML lifecycle | 7 | 9 | 7 | 7 | 7.5 | SOLID |
| 13 | Model serving | 7 | 9 | 9 | 8 | 8.3 | SOLID |
| 15 | Dynamic pricing RL | 8 | 10 | 9 | 5 | 8.0 | NEEDS WORK |

NEEDS WORK items, one per project:
- **03**: regenerate `threshold_sweep` with a subtitle that says "injected anomalies", not "real incidents".
- **08**: fix the `engine_panel` subtitle ("same gemma4:31b weights"), and pick one quantization label for the MLX 31B arm.
- **10**: persist the two-arm paired CIs in `reports/metrics.json` and gate them.
- **15**: add the five missing diagram specs.

## 3. Per-project notes

### 01 — RAG agent
- **Contents 8.** The article is clear and puts limits first: `final_v3` was read four times and is consumed, judging uses a single model family, and the corpus is capped (`story.yaml:207-210`). It names its floors (seeded random, lexical) and states negative results (first judge 39.7% miss rate, Set C crash; `:153`, Exact-numbers table). Problems:
  - Review-process wording: "reconciled … with the reviewer audit" (`story.yaml:154`; `README.md:77`).
  - Insider phrasing: "owner-labelled" / "owner audit" (`story.yaml:2,157,161,209,281`).
  - Heavy internal tags (`S3`, `final_v3`, `R0`) in the short version.
- **Results 9.** All checks verified:
  - F1 0.9091, precision 0.9524, TN 24/28 and unsupported 1 → `reports/final_v3_e2e/f1_summary.json` — verified.
  - recall@5 0.9457 → `reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json` `metrics.recall_at_5` 0.94565 — verified.
  - Faithfulness 0.8717; p50/p95 16.47/40.47 s → `final_v3_e2e/metrics.json` `detail.final_v3.faithfulness.mean`, `ops.*` — verified.
  - $0.0084/query = (0.781034 + 0.232599)/120 → `meter.phases.*.spend_usd` — verified. The cost basis string matches the article's $1.00/$4.00 rate card.
  - The result against the dense R0 baseline (0.9239) is modest and stated honestly.
- **Technologies 8.** FAISS + BM25 + RRF + cross-encoder is a current, sensible hybrid stack. Pydantic AI, RAGAS 0.3.1, a 4-stage DVC pipeline, 22 test files and committed traces are all present. The gap is that one model family drafts, verifies and grades. It is disclosed but not closed.
- **Visualizations 8.** Seven figures come from `src/rag_agent/figures.py`/`evaluate.py`, and the captions match the data. Minor issues:
  - `retrieval_ladder` y-window is 15× the data span (axes gate warning).
  - `chunk_size_sweep`/`model_comparison` titles say "65 golden questions" while the text says "tuning questions".

### 02 — Demand forecasting (M5)
- **Contents 8.** The no-CI limit, the quiet-day loss to the floor and the test-window reuse are stated. The `acf6f9f7` sentence explains the 0.6161 vs 0.6211 blend (2 vs 9 selection origins). That caption is now about 100 words (`story.yaml:241`). Conclusions keep "Results summary" first and put Limits last, unlike 01.
- **Results 9.** Verified:
  - 0.62105 vs floor 0.89290 → −30.45% (`reports_m5_full/metrics.json` `test.convex_ensemble` / `seasonal_naive`).
  - Best single fit 0.62192 (`test.lgbm_pool_store`).
  - Bias +0.0222, WAPE 0.7623, zero-day 0.5724 (`test.convex_ensemble`).
  - The ensemble edge over the best single fit (0.0008) is described as a near tie, which is honest.
- **Technologies 8.** LightGBM via mlforecast/statsforecast with the official 42,840-node WRMSSE is the right tool set. There are 6 DVC stages and 28 test files. The demo payload cannot be regenerated from the current metrics without a refit.
- **Visualizations 7.** Titles state findings. Two weaknesses:
  - The `m5_full_sample_series` title is honestly labelled "earlier-blend curve", but the figure still shows the superseded model.
  - The takeaway strings in `src/demand_forecasting/m5_full_figures.py` hard-code "0.6161 (weights 0.60/0.10/0.30)" and "under 0.001", which is a drift risk.

### 03 — Anomaly detection (NAB)
- **Contents 7.** Accurate, and it says "NAB score not reported". It is very dense. Problems:
  - A verbless intro at `story.yaml:22`.
  - The process phrase "(owner decision," at `README.md:92`.
- **Results 9.** Verified:
  - 1,609 raw alerts (`reports/nab_metrics.json` `overall.alerts_fired`).
  - Range precision 0.527, CI [0.230, 0.811] (`pa_k_2_precision_interval`).
  - The gain over the 16-seed no-skill band is stated honestly.
- **Technologies 8.** IsolationForest/OCSVM, range-PR and a seeded random band fit the problem, and there are 10 DVC stages. There is no official NAB scorer, and the article says so.
- **Visualizations 6.** The `threshold_sweep` subtitle reads **"17/120 flags hit real incidents"**. Its own caption says "17 of 120 flags hit injected anomalies" on the *synthetic* window. The title therefore contradicts the caption and the data source. Two smaller issues:
  - The `telemetry_flags` title says "Champion flags", and the file is 519 KiB (budget warning).
  - An unreferenced `score_distribution.json` is left in `reports/figures/`.
  - **Fix:** change the subtitle string in the generator to "injected anomalies" and regenerate offline.

### 04 — NLP classification + LLM cascade
- **Contents 7.** States that the cascade gain is not measurable and that HPO is inconclusive. Glossary asides in reader copy over-explain, and conclusions put Limits last.
- **Results 9.** Verified:
  - Fresh 0.953 → 0.954 (`reports/fresh_holdout.json` `runs.distilbert_full_120k`; `reports/llm_cascade.json` `fresh holdout.cascade_f1_macro` 0.95393).
  - $0.023671 (`llm_cascade.json` `ops.est_cost_usd`).
  - Test 0.9460 vs TF-IDF 0.8714 (`reports/metrics.json`).
- **Technologies 8.** DistilBERT, Optuna, a calibrated confidence gate and a data-scale ladder are all sound. Per-row cascade decisions are not persisted, so there is no paired CI, and the headline gate lists 04 as "uncovered" (`scripts/check_headline_numbers.py:33`).
- **Visualizations 8.** Seven figures, and the captions match.

### 05 — Churn pipeline (IBM Telco)
- **Contents 8.** The cost framing is clear. It separates the raw-model fairness slices from the served policy (caption `fairness_slices`). It cites the gitignored `data/operating_policy.json`; the committed equivalent is `reports/models/serving/meta.json`.
- **Results 9.** Verified:
  - $601 (`reports/metrics.json` `selected_model_calibrated.business_cost`).
  - $1,035 (`naive_majority.business_cost`; this is the contact-everyone cost, under a misleading internal key name).
  - CI [−508, −353] (`reports/sensitivity.json` `variants.fn5.cost_delta_ci`).
  - Threshold 0.175 (`reports/models/serving/meta.json`).
- **Technologies 8.** XGBoost/LightGBM, isotonic calibration, a cost curve, OOF threshold freezing and a sensitivity CLI. There are 10 test files.
- **Visualizations 8.** Seven figures. `permutation_importance` has no finding subtitle.

### 06 — Routing optimization (Solomon VRPTW)
- **Contents 8.** The fleet delta is always shown beside distance, and the hinted CP-SAT is disclosed as not independent. A process word remains in the roadmap: "owner-approved size" (`story.yaml:403`).
- **Results 9.** Verified:
  - Mean gap 4.2322%, CI [3.2232, 5.2815] (`reports/metrics.json` `intervals.mean_gap_pct`).
  - +3.73 vehicles (`summary.alns.mean_vehicle_delta`).
  - 1.150 s (`summary.alns.mean_runtime_s`).
  - The result is modest against the vehicle-first best-knowns, and the article says so.
- **Technologies 9.** ALNS with OR-Tools CP-SAT and PyVRP as references, a validator before scoring, and `tests/test_committed_solutions.py`.
- **Visualizations 8.** Seven figures with finding titles. `route_map_C101` comes from an f-string id, so a grep cannot find its generator.

### 07 — Open-data mobility (NYC TLC)
- **Contents 8.** The best selection discipline in the set: it serves the validation winner although XGBoost wins on test. Limits are explicit. The published docs page leaks process wording: "productionized (wave 15)" (`docs/projects/07-open-data-mobility.md:102`).
- **Results 9.** Verified:
  - 4.6763 vs 6.5175 MAE, −28.25% (`reports/metrics.json` `gbm_tuned.mae`, `naive_lag24.mae`).
  - p90 coverage 0.90795 (`reports/figures/p90_calibration.json`). This is figure data only and is not in `metrics.json`.
- **Technologies 8.** Polars, GeoPandas, LightGBM/XGBoost, conformal bands and drift reports, with 13 DVC stages. A rerun needs the 1.5 GB pinned download.
- **Visualizations 8.** Nine figures. `conformal_coverage` (90.7% → 91.5%, second half) and `p90_band` (90.8%, full window) use different subsets, and the captions explain this.

### 08 — LLM inference serving
- **Contents 6.** Two problems:
  - The quantization labels contradict each other. The MLX 31B is "unrecorded quantization" at `story.yaml:167` but "MLX 4-bit" at `:14,260,296`.
  - The docs page carries review-process voice: "both external audits' #1 recommendation" (`docs/projects/08-inference-serving.md:21`).
  - **Fix:** choose one label, backed by an artifact, and delete the audit phrase.
- **Results 9.** Verified:
  - p95 0.8114 s, p50 0.6315 s, 67.73 tok/s (`reports/metrics.json` `cells[0]`).
  - 32B arm 9.56 tok/s (`cells[12]`), so about 7×.
- **Technologies 6.** The harness is only httpx and plotly, with 5 test files and a single host. Quality is only a saturated format/keyword smoke check (the figure title says so), so the "serving choice" rests on speed alone. Re-measurement needs the same hardware.
- **Visualizations 6.** The `engine_panel` subtitle says **"same gemma4:31b weights"**, while its caption says "Quantization and packaging differ together". The title contradicts the caption. **Fix:** change the subtitle to "same model family", then regenerate.

### 09 — Agentic workflows
- **Contents 7.** Limits come first (n = 19, supervised pilot only). Problems:
  - It links readers into a review folder: `collaboration/reviews/20261118-live-confirmation/comparison.md` (`story.yaml:204`).
  - The docs page says "after the audit-P1 split" (`docs/projects/09-agentic-workflows.md:238`).
  - The short version uses process jargon ("live-grader", "h19 … calculator guard tripped").
- **Results 8.**
  - Verified: p95 31.102 s, median 18.227 s (`reports/metrics.json` `agentic_suite`, per-task); $0.00876/task (`agentic_suite.est_cost_usd_per_task`); held-out 13 answers / 6 should-fail / refusal 0.833 (`detail.heldout`).
  - **Not verified inside the project:** the live 13/13, 6/6 and 19/19 in the short version. They exist only in the review folder.
- **Technologies 8.** pydantic-ai/pydantic-evals 2.x, deterministic graders, HITL tests and recorded runs. The suites are small (Wilson lower bounds 0.77–0.80).
- **Visualizations 8.** Four figures, captions match, and the titles mark the run as "legacy recorded".

### 10 — Uplift experimentation (Hillstrom)
- **Contents 7.** Truthful and bounded: mail-everyone wins at $0.01, and the channel choice is unproven. The text is dense, and the two Qini interval protocols for one score are confusing side by side.
- **Results 7.**
  - Verified: +$2,812 (`reports/metrics.json` `t_learner.profit_delta_vs_random` 2812.34); random $4,026 (`profit_random_at_budget` 4025.80, so +69.9%); mail-everyone $16,103 (`random.profit_full`).
  - **Not verified machine-readably:** the headline CI [+$718, +$4,767]. It appears only in `reports/report.html`; `metrics.json` has no such field.
- **Technologies 7.** Cross-fitted T-learner, CUPED and DR/IPW are the right methods. The paired intervals are not persisted, so the headline gate checks the point only. An orphan `reports/demo_payload.json` has no demo.
- **Visualizations 7.** Nine figures with finding titles. The `qini_per_arm` x-window is 4.4× the data span.
- **Fix:** write the two-arm paired intervals into `metrics.json` and extend `_m10` in `scripts/check_headline_numbers.py` to cover them.

### 11 — DataFrame engines benchmark
- **Contents 9.** Parity comes before speed, and sqlite's load cost is explained. One navigation quirk: the text says the next figure is in Evaluation, but Training comes next (`story.yaml:123`).
- **Results 9.** Verified:
  - Polars 19.157× and DuckDB 14.886× (`reports/metrics.json` `summary.by_engine.*.geomean_speedup_vs_pandas`).
  - sqlite 0.035×, about 29× slower.
  - 1,658 trips (`tasks.join.engines.*.result[4].trips`).
- **Technologies 9.** Current engine versions are recorded in `reports/evaluation_metadata.json`. The canonical-result parity contract, fresh-process RSS probes and determinism tests are present.
- **Visualizations 8.** Five figures. The `speedup_overview` subtitle repeats numbers but states no finding.

### 12 — Tabular ML lifecycle (UCI bike sharing)
- **Contents 7.** The tie with LightGBM and the serial-dependence sensitivity are stated. The label "champion" is inconsistent:
  - `README.md:93-98` and `story.yaml:369-371` say "without a champion label".
  - `docs/projects/12-tabular-ml-lifecycle.md:24,61,63` and `reports/report.html` ("Champion: tabular MLP") still use the label.
  - `reports/metrics.json:38` says "per owner decision 8".
- **Results 9.** Verified:
  - MLP 25.4316, LightGBM 25.3732, floor 83.1994 (`reports/metrics.json`).
  - Validation tie −0.180 (`validation_tie_interval.point`).
  - CIs [52.5, 63.1], [44.2, 71.8] and [38.8, 73.4] (`reports/results.md:17`).
- **Technologies 7.** Seeded PyTorch MLP, LightGBM with Optuna, and block bootstraps. The committed run keeps a known pruning defect (the pruning rule drops `atemp`, the higher-MI feature of the correlated pair) and uses positional lags across a 36-hour gap. Both are disclosed.
- **Visualizations 7.** 11 figures. The `bootstrap_ci` axis reads "MAE(floor) - MAE(champion)", while its caption says "served-model".

### 13 — Model serving (FastAPI / ONNX / Docker)
- **Contents 7.**
  - At HEAD, the copy is clean ("served MLP"). A residual label "Champion re-derivation:" remains in `reports/results.md:5` and `reports/evaluation_metadata.json:2` (generated from `src/model_serving/report.py:147`).
  - **The live app still shows "champion" 11 times** (see §0).
- **Results 9.** Verified:
  - 25.43163 reproduction (`reports/metrics.json` `reproduction.derived_test_mae`).
  - Parity 7.15e-07 (`parity.max_abs_scaled`).
  - Image 6466.5 MB (`docker.total_mb`); slim image 291.2 MB (`reports/docker_slim.json`).
  - p50 0.00163 s (`serving.native.concurrency.c1.p50_s`).
- **Technologies 9.** FastAPI, ONNX Runtime with a parity gate, an exact reproduction gate, a measured multi-stage Docker build and a slim image. The 65 W energy assumption differs from 08's 100 W on the same class of host.
- **Visualizations 8.** Four figures, captions match, and all six diagrams render on the live page (browser read).

### 15 — Dynamic pricing RL
- **Contents 8.** A model negative result. The comparator is preregistered, the CI is paired, the limits are explicit (simulator only, assumed elasticity), and the article says "we would not deploy". Problems:
  - Process voice: "The owner committed the frozen params" (`story.yaml:84`).
  - A "; next, the" splice at `:117`.
  - Conclusions have only `## Limits`. There is no Exact numbers or Protocol block, unlike every other project.
- **Results 10.** Every check verified against `reports/metrics.json`:
  - RL 0.5120, B1 0.5217, UB 0.5291 (`test.policies.*.mean_normalised_profit`).
  - −1.858% and CI [−0.011437, −0.007998] (`primary`).
  - Bound share 96.76% / 98.60%, and by rho 97.36 / 96.90 / 95.74 (`fluid_bound_share_by_rho`).
  - Stress: 0.5450 / 0.5649 / 0.5356 and 0.4817 / 0.4837 / 0.4753 (`stress.*`).
  - 0 violations (`constraint_gate`).
  - `reports/test_episodes.json` is 1,297,936 B (≈1.2 MiB).
  - `reports/sealed_access.json` holds exactly 3 reads.
- **Technologies 9.** Exact pins (`gymnasium==1.4.0`, `stable-baselines3==2.9.2`, `sb3-contrib==2.9.2`), MaskablePPO with action masks, common random numbers, a preregistration hash, an append-only seal log and 11 test files. Elasticity is an assumption, and the article says so.
- **Visualizations 5.** The four figure titles state findings and match the data. However, **none of the five diagram fences resolves** in source: `15-pricing-pipeline` and `auto-15-dynamic-pricing-rl-1` to `-4` are not under `apps/showcase-web/src/diagrams/`. On the live page, the browser pane showed "Unknown diagram spec." fallback boxes for four of the five ids, with the fifth still loading. **Fix:** author the five specs, register them in `diagrams/index.ts`/`auto/index.ts`, and add a fence-resolution gate.

## 4. Portfolio-level summary

**Verdict.** At HEAD the portfolio is truthful: every headline number spot-checked across 14 projects matches a committed artifact, and no article overclaims against its baseline. Two problems remain. The live app is two commits behind `main`, so the Wave 8 fixes are not what readers see. Four projects have a concrete defect in a figure, a diagram or the evidence behind a headline.

**Strongest / weakest per axis**
- Contents: strongest 11 (9). Weakest 08 (6: contradicting quantization labels and audit voice).
- Results: strongest 15 (10: every number in one gated metrics file). Weakest 10 (7: headline CI only in HTML).
- Technologies: strongest 06, 11, 13 and 15 (9). Weakest 08 (6: no quality evaluation, thin harness).
- Visualizations: strongest 01, 04–07, 09, 11 and 13 (8). Weakest 15 (5: diagrams missing on the live page).

**Cross-project inconsistencies**
1. **Deploy lag.** The app is at `c05accd0` and the docs site is at HEAD, so the two public surfaces disagree (13 "champion" ×11 live vs 0 in docs).
2. **"Champion" label.** 12's README and story avoid it, but 12's docs page, `report.html` and `bootstrap_ci` axis still use it, as do 13's `results.md:5` and 03's `telemetry_flags` title.
3. **Review-process voice in published copy:**
   - 01 `story.yaml:154` ("reviewer audit")
   - 03 `README.md:92`
   - 06 `story.yaml:403`
   - 07 `docs/…:102` ("wave 15")
   - 08 `docs/…:21`
   - 09 `story.yaml:204` (review-folder link) and `docs/…:238`
   - 12 `metrics.json:38`
   - 15 `story.yaml:84`
4. **Conclusions structure.** There are three shapes:
   - 01/03/12 follow Taught → Limits → Exact → Protocol.
   - 02, 04–11 and 13 put Results summary first and Limits last.
   - 15 has Limits only.
5. **Headline evidence outside `metrics.json`:**
   - 07 coverage is in figure JSON only.
   - 10 CIs are in HTML only.
   - 12 block CIs are in `results.md` only.
   - 09's live numbers are in a review folder.
6. **Energy assumptions.** 08 uses 100 W and 13 uses 65 W on the same class of host, so their cost lines are not comparable.
7. **Gate coverage gaps.** No gate checks that diagram fences resolve (which is how 15 shipped with fallbacks), and 04 is "uncovered" in the headline gate.

**Three most valuable follow-ups**
1. **Redeploy the app from `acf6f9f7` and verify it:** `/health` sha = HEAD, and the live 13 story has 0 "champion" hits. Without this, Wave 8 is not live for readers.
2. **Fix the four NEEDS WORK items:**
   - 15: add the five diagram specs, plus a `check_diagram_fences.py --check` gate over every story.
   - 03: change the `threshold_sweep` subtitle to "injected anomalies".
   - 08: fix the `engine_panel` subtitle and pick one quantization label.
   - 10: persist the paired CIs to `metrics.json` and gate them.
3. **One copy-hygiene pass across the portfolio:**
   - Remove the review-process phrases listed in item 3 above.
   - Finish the "champion" cleanup in 12, 13 `results.md` and 03.
   - Move 09's live evidence under `projects/09-agentic-workflows/reports/`.
   - Align the conclusions order (including 15's missing Exact/Protocol blocks).

Not verified in this pass: the full pytest/npm/mkdocs suites, and the visual rendering of every live page. The browser pane was used only for the 15 and 13 pages. On those pages it read the diagram fallbacks, the count of rendered flow diagrams, the "champion" count and the build sha.
