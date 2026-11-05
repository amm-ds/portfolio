# Production review — 2026-11-06

Artifact-only review of the 13 experiments. No training, evaluation, serving, or
DVC pipeline was re-run. No file under `apps/agent-chat/**` or any diagram
specification was changed.

## Method and status semantics

Checks per project:

- **(a) Pipeline:** `dvc.yaml` exists and the README documents a `dvc repro`
  path. Presence is not a claim that every manual side track is in DVC.
- **(b) Tests/CI:** `tests/` exists and the newest test-executing main CI run is
  green for that project.
- **(c) Metrics:** `reports/metrics.json` exists and three headline values agree
  with the committed primary metrics. Projects 02, 03, and 04 keep their primary
  headline in the documented sidecars `reports_m5_full/metrics.json`,
  `reports/nab_metrics.json` + `reports/nab_sweep.json`, and
  `reports/fresh_holdout.json`; their base `reports/metrics.json` covers an
  older/synthetic track and was not substituted for the headline.
- **(d) Story:** the eight ids are exactly `background, objectives, data, eda,
  training, evaluation, results, conclusions`; every section ends with a
  `**Business summary:**` card; the roadmap has 4–7 items and delivered items
  only. Project 02's deferred full-panel refinement re-run is the explicit
  exception.
- **(e) Demo:** the 02/05 committed payload agrees with the headline, including
  the pooled/full-panel chips and served operating point. N/A elsewhere.
- **(f) Data card:** the story's `data` section links its dataset card. Project
  08 is synthetic-only and explicitly needs no download or external card.
- **(g) README:** the house equivalents of What/Why/Quickstart/Results/Limits/
  Reproduce are present, plus a `## Common errors` table with an executable fix.

`PASS (fixed)` was a proven failure during the review and is corrected in this
working tree. `FAIL` remains open. Values below are copied from the cited JSON,
not recalculated by a pipeline.

### CI evidence

`gh run list --workflow ci.yml --branch main` returned latest run
[42101903091](https://github.com/amm-ds/portfolio/actions/runs/42101903091)
(`fe100d3a1a0257f5845bf8b979bafd14aaf3dec3`, overall success), but its tests
job was skipped. The newest main run that actually executed the project matrix
is [42083306015](https://github.com/amm-ds/portfolio/actions/runs/42083306015)
(`147440e2eedd8ac157713fe65b7a5550a411367c`). Its `02-unit`, `02-models`, and
01/03/04/05/06/07/08/09/10/11 cells all succeeded. The matrix at
`.github/workflows/ci.yml` has no 12 or 13 suite, so a green workflow is not
green evidence for those projects.

## Summary

| Project | (a) | (b) | (c) | (d) | (e) | (f) | (g) |
|---|---|---|---|---|---|---|---|
| 01 RAG agent | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| 02 Demand forecasting | PASS | PASS | PASS | PASS | PASS | PASS (fixed) | PASS |
| 03 Anomaly detection | PASS | PASS | PASS | PASS | N/A | PASS (fixed) | PASS |
| 04 NLP classification | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| 05 Churn pipeline | PASS | PASS | PASS | PASS | PASS (fixed) | PASS | PASS (fixed) |
| 06 Routing optimization | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| 07 Mobility | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| 08 Inference serving | PASS (fixed) | PASS | PASS | PASS | N/A | PASS (synthetic) | PASS |
| 09 Agentic workflows | PASS | PASS | PASS | PASS | N/A | PASS (fixed) | PASS |
| 10 Uplift | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| 11 DataFrame engines | PASS | PASS | PASS | PASS (fixed) | N/A | PASS | PASS |
| 12 Tabular lifecycle | PASS | **FAIL** | PASS | PASS | N/A | PASS | PASS |
| 13 Model serving | PASS | **FAIL** | PASS (fixed) | PASS | N/A | PASS (fixed) | PASS |

Only checks (b) for 12 and 13 remain failed.

## Per-project evidence

### 01 — RAG & Agentic AI Assistant

- **(a) PASS:** `projects/01-rag-agent/dvc.yaml`; `README.md` → Reproduce gives
  `dvc repro` and `dvc metrics show`.
- **(b) PASS:** 15 files under `projects/01-rag-agent/tests/`; green `01-rag-agent`
  cell in CI 42083306015.
- **(c) PASS:** `reports/metrics.json` → `retrieval_chunks_200.recall@5 =
  0.8307692307692308` (story 0.831/83%), `_meta.taxonomy.unsupported-claim = 18`
  (18/65), `ragas.faithfulness = 0.6848` (0.685).
- **(d) PASS:** `story.yaml` has the eight ordered ids, eight trailing business
  cards, and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS:** `story.yaml` → data links
  `https://amm-ds.github.io/portfolio/data-registry/wikipedia/`; the card is
  `docs/data-registry/wikipedia.md`.
- **(g) PASS:** `README.md` has Problem/Design/Results/Limits/Reproduce and
  Common errors with provider setup commands.

### 02 — Hierarchical Demand Forecasting

- **(a) PASS:** `projects/02-demand-forecasting/dvc.yaml`; `README.md` →
  Reproduce gives `uv run dvc repro projects/02-demand-forecasting` and the
  separate full-panel CLI path.
- **(b) PASS:** 27 test files; green `02-unit` and `02-models` cells in CI
  42083306015.
- **(c) PASS:** `reports_m5_full/metrics.json` → `series_universe.n_series =
  30490`, `hierarchy.n_nodes_total = 42840`,
  `test.convex_ensemble.official_wrmsse = 0.6160835041498506`, and
  `test.seasonal_naive.official_wrmsse = 0.8928984140422355`; these render as
  30,490, 42,840, 0.6161, and 0.8929.
- **(d) PASS:** eight ids/cards; six delivered items plus the explicitly allowed
  deferred full-panel refinement re-run.
- **(e) PASS:** `reports_m5_full/demo_payload.json` → `groups.headline` repeats
  0.6160835041498506; `groups.test_pooled` matches the metrics for naive
  (0.8928984140422355), pooled store (0.6216694113969415), pooled store×cat
  (0.6574865460657008), pooled dept (0.6312795744299703), and the ensemble.
- **(f) PASS (fixed):** the data section initially had no dataset-card link; it
  now links `data-registry/m5-nixtla-mirror/`, backed by
  `docs/data-registry/m5-nixtla-mirror.md`.
- **(g) PASS:** README skeleton and Common errors are present.

### 03 — Anomaly Detection over Telemetry

- **(a) PASS:** `projects/03-anomaly-detection/dvc.yaml`; `README.md` →
  Reproduce gives `dvc repro projects/03-anomaly-detection`.
- **(b) PASS:** 14 test files; green `03-anomaly-detection` cell in CI
  42083306015.
- **(c) PASS:** `reports/nab_metrics.json` → `overall.events_detected = 16`,
  `events_missed = 1`, `alerts_fired = 1609`, `pr_auc = 0.5271388295453142`;
  `reports/nab_sweep.json` → the IsolationForest rolling+residual budgeted
  stream has `alerts_fired = 80`, and ensemble+rolling has 35. These support
  16/17, 1,609, and 80 (and the separate 35-page comparison).
- **(d) PASS:** eight ids/cards and seven delivered roadmap items.
- **(e) N/A.**
- **(f) PASS (fixed):** the story data section initially had no card link; it
  now links `data-registry/nab/`, backed by `docs/data-registry/nab.md`.
- **(g) PASS:** README skeleton and Common errors are present.

### 04 — NLP Classification with Transformers

- **(a) PASS:** `projects/04-nlp-classification/dvc.yaml`; `README.md` →
  Reproduce gives `dvc repro projects/04-nlp-classification`.
- **(b) PASS:** 13 test files; green `04-nlp-classification` cell in CI
  42083306015.
- **(c) PASS:** `reports/fresh_holdout.json` → full-data
  `runs.distilbert_full_120k.f1_macro = 0.9529432473490507` (95%), TF-IDF
  `runs.baseline_tfidf_logreg.f1_macro = 0.8785374076223136` (88%), and the
  τ=0.50 cascade row has `escalation_rate = 0.246` (75.4%, about 3/4, stays on
  the keyword path). The routed score is `0.9020481367529292`, not 0.9529.
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS:** data links `data-registry/ag-news/`; card:
  `docs/data-registry/ag-news.md`.
- **(g) PASS:** README skeleton and Common errors are present.
- **Copy correction:** the short version/card claim “keeps that quality” was
  false against the same artifact: router 0.9020 versus full-data 0.9529. It now
  says the router beats either bounded model at keyword cost for 3 of 4 items.
  The Background card was corrected the same way. All 52 short-copy surfaces
  were regenerated/checked.

### 05 — Churn Modeling with sklearn Pipelines

- **(a) PASS:** `projects/05-ml-pipeline-churn/dvc.yaml`; `README.md` →
  Reproduce gives `dvc repro projects/05-ml-pipeline-churn`.
- **(b) PASS:** 10 test files; green `05-ml-pipeline-churn` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` → `_meta.calibrated_opt = 0.175`,
  `selected_model_calibrated.business_cost = 601.0`,
  `naive_majority.business_cost = 1035.0`; `_meta.cost_delta_ci` is point −416,
  interval [−485, −343].
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) PASS (fixed):** the payload's costs and CI already matched, but
  `reports/demo_payload.json` had `model.threshold_selected = 0.15`, the raw
  model's optimum, while the served/headline optimum is 0.175. The generator
  used `_meta.selected_opt`. It now uses `_meta.calibrated_opt`; the metrics
  writer persists that key, the payload is 0.175, and the Python/Vitest payload
  contracts pin it. Independent corroboration:
  `reports/models/serving/meta.json` → `threshold_selection.threshold = 0.175`.
- **(f) PASS:** data links `data-registry/telco-churn/`; card:
  `docs/data-registry/telco-churn.md`.
- **(g) PASS (fixed):** the README had no standalone Limits section and no
  Common errors block. Both were added; the latter gives `brew install libomp`
  followed by the project pytest command.

### 06 — Routing Optimization (VRPTW)

- **(a) PASS:** `projects/06-routing-optimization/dvc.yaml`; `README.md` →
  Reproduce gives `dvc repro projects/06-routing-optimization/dvc.yaml`.
- **(b) PASS:** eight test files; green `06-routing-optimization` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` → `summary.alns.mean_gap_pct = 4.2322`,
  `mean_runtime_s = 1.150169`, `mean_vehicle_delta = 3.73`; story 4.23%, about
  one second, +3.73 vehicles.
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS:** data links `data-registry/cvrplib-solomon/`; card:
  `docs/data-registry/cvrplib-solomon.md`.
- **(g) PASS:** README skeleton and Common errors are present.
- **Copy correction:** the README data bullet said “subset of 10 instances”
  while its results and `metrics.json` cover all 56. It now says the full set of
  56.

### 07 — Urban Mobility Demand Intelligence

- **(a) PASS:** `projects/07-open-data-mobility/dvc.yaml`; `README.md` →
  Reproduce documents `dvc repro`.
- **(b) PASS:** 12 test files; green `07-open-data-mobility` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` → `gbm_tuned.mae =
  4.676299418090131`, `deltas.gbm_tuned.mae_reduction_pct = 28.25`, and
  `_meta.p90_coverage = 0.9079498337194689`; story 4.676, 28.3%, 90.8%.
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS:** data links both `data-registry/nyc-tlc/` and
  `data-registry/noaa-ghcn/`; cards exist under `docs/data-registry/`.
- **(g) PASS:** README skeleton and Common errors are present.

### 08 — LLM Inference & Serving

- **(a) PASS (fixed):** `projects/08-inference-serving/dvc.yaml` exists, but the
  README named stages without a reproduction command. Its CLI block now includes
  `uv run dvc repro`.
- **(b) PASS:** four test files; green `08-inference-serving` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` has 19 cells, 760 total requests, and 0
  failures. The qwen3.6 c=1 cell has `p95_latency_s = 0.8114235829561949`
  (0.81 s), `p50_latency_s = 0.6315026249503717`, and zero failures.
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS (synthetic):** data says the eight prompts are built locally,
  “Nothing is downloaded, so no license applies”; no external dataset card is
  applicable.
- **(g) PASS:** CLI is the Quickstart equivalent; Results/Limits/Tests/Common
  errors are present.

### 09 — Agentic Workflows

- **(a) PASS:** `projects/09-agentic-workflows/dvc.yaml`; `README.md` →
  Reproduce documents `dvc repro` and the held-out CLI path.
- **(b) PASS:** eight test files; green `09-agentic-workflows` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` → `agentic_suite.success_rate = 1.0` and
  `detail.n_tasks = 15` (15/15); `detail.heldout.n_answer = 13` with
  `answer_success = 1.0` (13/13); `n_should_fail = 6` with
  `should_fail_pass_rate = 0.833` (5/6).
- **(d) PASS:** eight ids/cards and six delivered roadmap items.
- **(e) N/A.**
- **(f) PASS (fixed):** the data section had no dataset-card link; it now links
  `data-registry/wikipedia/`, backed by `docs/data-registry/wikipedia.md`.
- **(g) PASS:** README skeleton and Common errors are present.

### 10 — Uplift & Experimentation

- **(a) PASS:** `projects/10-uplift-experimentation/dvc.yaml`; `README.md` →
  What runs gives `uv run dvc repro`.
- **(b) PASS:** seven test files; green `10-uplift-experimentation` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` →
  `t_learner.profit_delta_vs_random = 2812.3425124175596` (+$2,812; +69% at the
  committed budget), `_meta.ci.t_learner_vs_random.profit_at_budget_diff_ci =
  [717.5813496189148, 4766.662824368375]`, and
  `treat-everyone.profit_full = 16103.217226133487`.
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS:** data links `data-registry/hillstrom/`; card:
  `docs/data-registry/hillstrom.md`.
- **(g) PASS:** README skeleton and Common errors are present.

### 11 — DataFrame Engines Benchmark

- **(a) PASS:** `projects/11-data-engineering/dvc.yaml`; `README.md` → Common
  errors documents `uv run dvc repro`; the CLI real/synthetic paths are in
  Reproduce.
- **(b) PASS:** five test files; green `11-data-engineering` cell in CI
  42083306015.
- **(c) PASS:** `reports/metrics.json` → `dataset.n_rows = 2964624`,
  `summary.by_engine.polars.geomean_speedup_vs_pandas = 19.157`, and DuckDB
  14.886; story 2.96M, 19x/19.2, and 15x/14.9.
- **(d) PASS (fixed):** eight ids/cards. The roadmap initially appended a
  deferred out-of-core item despite the delivered-only contract; it was removed,
  leaving four delivered items (the deferred scope remains described in Limits).
- **(e) N/A.**
- **(f) PASS:** data links `data-registry/nyc-tlc/`; card:
  `docs/data-registry/nyc-tlc.md`.
- **(g) PASS:** README skeleton and Common errors are present.

### 12 — Tabular ML & Deep Learning Lifecycle

- **(a) PASS:** `projects/12-tabular-ml-lifecycle/dvc.yaml`; `README.md` →
  Reproduce gives `dvc repro`.
- **(b) FAIL:** five test files and 34 statically named test functions exist,
  but `.github/workflows/ci.yml` → `jobs.tests.strategy.matrix.suite` has no 12
  entry. CI 42083306015 therefore provides no green 12 run; latest CI 42101903091
  skipped tests altogether. Local tests were not substituted for missing CI
  evidence.
- **(c) PASS:** `reports/metrics.json` → `mlp.mae = 25.43163249606178`,
  `seasonal_naive.mae = 83.19940476190476`, and
  `_meta.mae_improvement_vs_floor_ci = {point: 57.76777226584298,
  lo: 52.48709735714254, hi: 63.0707142345962}`; story 25.4, 83.2, 57.8
  [52.5, 63.1].
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS:** data links `data-registry/bike-sharing/`; card:
  `docs/data-registry/bike-sharing.md`.
- **(g) PASS:** README skeleton and Common errors are present.

### 13 — Model API Serving & Docker Deployment

- **(a) PASS:** `projects/13-model-serving/dvc.yaml`; `README.md` → Pipeline
  gives `uv run dvc repro`.
- **(b) FAIL:** seven test files and 30 statically named test functions exist,
  but `.github/workflows/ci.yml` → `jobs.tests.strategy.matrix.suite` has no 13
  entry. There is no green project cell in the newest test-executing run, and
  the newest run skipped tests.
- **(c) PASS (fixed):** `reports/metrics.json` → reproduction derived/expected
  MAE both 25.43163249606178, `parity.max_abs_scaled =
  7.152557373046875e-07`, ONNX c=1 `p50_s = 0.0015844160225242376` (1.6 ms),
  ONNX batch-128 throughput 57,451.30910794788 rows/s (about 56k). The short
  copy previously said 1.7 ms and the Exact numbers table contained an older
  benchmark (for example c=64 93.0/340.3/489.5 ms and 452 req/s). Both now match
  the committed current cells: ONNX c=64 is 63.1/209.8/290.9 ms and 715 req/s;
  all eight exact-table rows were refreshed.
- **(d) PASS:** eight ids/cards and five delivered roadmap items.
- **(e) N/A.**
- **(f) PASS (fixed):** the data section initially had no card link; it now
  links `data-registry/bike-sharing/`, backed by
  `docs/data-registry/bike-sharing.md`.
- **(g) PASS:** README skeleton and Common errors are present.

## Public-docs coherence

### Surface comparison

- **Thirteen experiments:** root `README.md` has 13 project rows and says
  “Thirteen projects”; `docs/projects/index.md` has 13 rows and says “Thirteen
  showcases”; `cardCopy.ts` has 13 ids in each card map; all 13 stories have a
  `short_version`. `docs/index.md` only said “A growing set”, so it now says
  “Thirteen reproducible case studies”. The GitHub repository description says
  “Thirteen end-to-end ML/AI systems”, fetched read-only with
  `gh repo view amm-ds/portfolio --json description`. The profile README says
  “thirteen end-to-end systems”, fetched read-only with
  `gh api repos/amm-ds/amm-ds/contents/README.md`.
- **Apps block:** present on the public web Projects page at
  `apps/showcase-web/src/pages/ProjectsIndex.tsx` → `apps-block`, sourced from
  `apps/showcase-web/src/lib/apps.ts`. The root README also identifies the
  FastAPI + React showcase, and the profile identifies the FastAPI showcase and
  React front end. No agent-chat source/spec was changed.
- **Project 11 title:** “DataFrame Engines Benchmark” agrees across the root
  README, docs Projects index/page, `projects/11-data-engineering/portfolio.yaml`
  and README, and the generated static registry. The NYC TLC card said “Data
  Engineering Benchmark” and was aligned to the same title.
- **Stale counts:** no stale Ten/Eleven portfolio count exists in the requested
  surfaces. The current runbook `docs/runbooks/pipeline-restore.md` did say “all
  ten projects” and now says all thirteen. “Ten data tasks” in project 11 is a
  task count, not a stale portfolio count. Dated audit documents were left as
  historical records.
- **02/05 demo coherence:** pooled M5 chips match exactly; the churn payload's
  raw-model threshold drift was fixed as detailed above.
- **04/13 copy coherence:** the router-quality claim and the model-serving
  latency/table drift were fixed against their committed JSON, and all short
  copy surfaces were synchronized.

### Gates run after the fixes

- `uv run python scripts/check_short_copy.py --check` — **PASS**, 52 surfaces
  across 13 stories.
- `uv run python scripts/check_docs.py` — **PASS**, `check-docs: OK`.
- `uv run python scripts/gen_static_registry.py --check` — **PASS**, current.
- `uv run python scripts/gen_story_short.py --check` — **PASS**, current.
- `uv run python scripts/check_demo_contract.py` — **PASS**, both demos and the
  static registry snapshot.
- `uv run python scripts/lint_story_language.py` — **PASS**, 13 stories, 0
  errors, 0 warnings.
- `uv run mkdocs build --strict` — **PASS** (existing nav informational notices
  only).
- `uv run pytest projects/05-ml-pipeline-churn/tests/test_demo_payload.py -q` —
  **PASS**, 7 tests.
- `npm test -- --run src/demos/churn-sandbox/payload.test.ts` from
  `apps/showcase-web` — **PASS**, 5 tests.
- Ruff check/format-check on the changed churn Python files — **PASS**.

## Skipped items and residual risks

- **12/13 CI coverage is unresolved.** The review did not alter CI or claim a
  local run was CI. Add both suites to `.github/workflows/ci.yml`, then verify a
  later main run before changing (b) to PASS.
- **The latest CI's green status is not a test signal.** Run 42101903091 skipped
  the test matrix and had a non-blocking `a11y-axe` failure. The scorecard uses
  the newest run that actually executed tests instead.
- **DVC presence is not complete side-track coverage.** Project 02's full M5
  headline is documented through `evaluate-m5-full`, not its legacy `dvc.yaml`;
  03's sweep/tune/refine commands are documented outside DVC; 04's full-data and
  fresh-holdout paths and 09's held-out path are manual. These are explicit
  reproduction-coverage risks, not hidden by check (a).
- **Diagram specifications were excluded as instructed.** In particular,
  `apps/showcase-web/src/diagrams/servingPipeline.ts` still says “1.7 ms p50”;
  the owning agent should reconcile it to the committed 1.6 ms values. No
  diagram file was edited here.
- **GitHub metadata was read-only.** The repository description and profile
  README were consistent, so no outward-facing update was needed or attempted.
- **Historical audits were not rewritten.** Their old ten-project statements are
  date-stamped history, unlike the current runbook corrected above.
