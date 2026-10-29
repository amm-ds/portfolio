# Portfolio Audit — github.com/amm-ds

**Audited:** 2026-10-16 · **Scope:** GitHub profile, all 5 public repos, docs site (amm-ds.github.io/portfolio), code, tests, CI, commit history.

---

## 1. Executive summary

The `portfolio` repo is, in engineering-artifact terms, one of the strongest data-science portfolio repos you will see: a `uv` monorepo with 9 numbered showcases, shared typed libraries, 7 architecture decision records, DVC pipelines per project, a data registry with checksum-pinned dataset cards, ~513 test functions across 110 test files, CI with coverage gates + CodeQL + Docker smoke test, a FastAPI + React/TypeScript showcase app, per-project DESIGN docs, and runbooks. Reporting is unusually honest (negative results are kept and explained).

The weaknesses are not in the code — they are in **credibility and reach**:

1. **The entire portfolio was built in ~4 days** (64 commits, 2026-10-12 → 2026-10-16) and the repo itself contains the commissioning brief addressed to "a coding agent" (`docs/repository_setup_report_senior_data_scientist.md`). A technical evaluator who notices this will discount the "seniority" signal heavily.
2. **Zero external validation**: 0 stars, 2 followers, no OSS contributions, no public deployment of the showcase app (localhost only), all metrics self-reported from local runs.
3. **Profile hygiene**: empty bio, no profile README, no public email (while the About page tells clients to find the email "on the GitHub profile"), and **3 of 5 repos are empty placeholders** with title-only READMEs — they actively subtract credibility.
4. **Internal inconsistencies**: the root README says project 08 is "planned" while its docs show it complete with real benchmark results; the projects table omits 08 and 09 entirely; the repo description says "7 showcases".

**Overall weighted score: 7.7 / 10** — architect-level engineering artifacts, junior-level public presence.

---

## 2. Scores by dimension

| Dimension | Score | Evidence |
| --- | --- | --- |
| Architecture & system design | **9.5** | 7 ADRs with real trade-off reasoning, reference architecture doc, shared `portfolio-core` / `portfolio-eval` libs, pydantic contracts at every boundary, scaffold script for new projects |
| Reproducibility & MLOps | **9.0** | Committed `uv.lock`, per-project `dvc.yaml`/`dvc.lock`, dataset cards with URLs + sha256, `make setup && dvc repro` contract, release-verify gate. Missing: DVC remote storage (`.dvc/config` is empty — artifacts can't be fetched, only regenerated) |
| Documentation & storytelling | **9.0** | Every project: DESIGN.md + case study (background → data → EDA → evaluation → honest delta), `story.yaml` per project, runbooks, engineering playbook. MkDocs site live (HTTP 200) |
| Code quality | **8.5** | Clean, idiomatic, well-docstringed Python; ruff + mypy (strict on shared libs); typed TS frontend. Some oversized modules (`evaluate.py` 24KB, `reporting.py` 18.5KB, `cli.py` 16KB) that should be split |
| Testing & CI | **8.5** | ~513 test functions, property-based tests (hypothesis) on validators, CI gate = lint + types + tests + frontend build + docs strict build + Docker smoke. The 55% coverage floor for projects/apps is lenient vs the 80% libs floor |
| Evaluation rigor & data realism | **8.0** | Real data in 01 (Wikipedia), 04 (AG News), 06 (CVRPLIB Solomon), 07 (NYC TLC 41.2M trips + NOAA); naive baselines everywhere; negative results kept (LOF "structurally blind", temporal_net trails ridge). But 02/03/05 headline on synthetic data, and LLM evals bounded to 10/26 questions |
| Project breadth & depth | **8.5** | Agentic AI, forecasting, anomaly detection, NLP, classical ML, combinatorial optimization, data engineering, LLM serving, agentic workflows — exceptional range on one platform. 08/09 are thinner (bounded runs) |
| Consistency & polish | **6.5** | Stale README (08 "planned" but complete; table missing 08/09; description says 7 showcases; description vs README count drift); `architecture` and `data-registry` exist both at root and under `docs/` (near-duplicate stub files); pokemon repo has a 35KB GPL LICENSE with no code |
| Credibility & authenticity | **5.0** | Built in 4 days by an agent (brief committed in-repo); all metrics unverifiable local runs; no external engagement. The honesty of keeping the brief is admirable, but as committed it reads as "principal-level portfolio, commissioned from an AI" |
| Discoverability & reach | **4.0** | Good repo topics + live Pages site, but: no profile README, empty bio, no public email, 2 followers, 0 stars, showcase app not deployed anywhere public, no LinkedIn/site link on profile |

**Weighted overall: 7.65 / 10.**

---

## 3. Profile-level findings (outside the main repo)

| Item | State | Recommendation |
| --- | --- | --- |
| `amm-ds/amm-ds` profile README | Missing | Create it: 5-line positioning, 3 flagship links with one figure each, contact CTA |
| Bio / email / website | All empty | Add bio ("Freelance ML/AI engineer — agentic AI, forecasting, MLOps"), public email, link to the Pages site. The About page currently sends clients to a profile email that doesn't exist |
| `pokemon_tgc_dashboard` | README title + GPL license, **no code** | Either build it (it would fill the "consumer-facing dashboard" gap) or delete it |
| `nitxla_time_series_wrapper` | README title only | Delete, or fold the idea into project 02 as a documented extension |
| `data_science_examples` | README title only | Delete — superseded by the portfolio monorepo |
| `llamaindex_query_engine_agent` (2024) | Complete-ish LlamaIndex agent with eval harness; commits vector stores and `.pkl` artifacts | Add a "superseded by portfolio project 01" banner, clean the committed artifacts, or archive the repo read-only |

---

## 4. Per-project review

### 01 — RAG & Agentic AI Assistant — **9.0** (flagship)

Strong: pydantic-ai agent with citation-enforced structured output, chunk-size sweep, cross-encoder rerank, recall@5 0.962 vs 0.038 random, cost telemetry, RAGAS with a local judge. Honest scoping (LLM phases on 10 questions, stated plainly).
Improvements:

- Scale the LLM-phase eval from 10 → all 26 questions (run once overnight; the current bound is the weakest link in the flagship).
- Add a **faithfulness regression gate** in CI: replay the 26-question golden set against the deterministic mock provider and assert citation-coverage ≥ threshold, so prompt edits can't silently degrade grounding.
- Add adversarial/out-of-corpus questions to prove the refusal path (confidence < 0.3) actually fires — currently asserted in the prompt, not demonstrated in results.
Visualizations to add: retrieval recall@k curve per chunk size overlaid with context-token cost; a citation-coverage heatmap (question × supporting passage); a "refusal calibration" scatter (confidence vs correctness).

### 02 — Hierarchical Demand Forecasting — **8.0**

Strong: leakage-proof time-CV, Optuna HPO, GBM −41.1% vs persistence, MinT-lite reconciliation, honest PyTorch-vs-ridge result, real-data UCI track that exposes where synthetic breaks (89% zeros).
Improvements:

- The synthetic-vs-UCI divergence is the most interesting finding in the project — promote it from a footnote to a headline section ("what breaks on real intermittent demand").
- Add a proper intermittent-demand model (Croston/TSB) since zeros are the documented failure mode.
- Finish calibrated prediction intervals (own roadmap item).
Visualizations: fan charts of p10/p50/p90 per series; zero-inflation histogram per series; reconciliation error waterfall (base → reconciled coherence gain).

### 03 — Anomaly Detection over Telemetry — **8.0**

Strong: detector HPO rescue story (OCSVM 0.34 → 0.91 ROC-AUC), honest LOF failure, streaming probe, NSL-KDD real-data probe (0.882), DQ gates.
Improvements:

- NSL-KDD is a 1999-era dataset with known artifacts — add a modern benchmark (e.g., a recent CIC IDS set) or acknowledge the limitation explicitly in the README.
- Add alert-budget economics: precision at fixed false-alarm rate per day, the metric ops teams actually buy.
Visualizations: PR curves (not just ROC) under class imbalance; score-distribution ridge plots per detector; threshold sweep with cost curves; streaming detection-delay chart (time-to-detect vs anomaly onset).

### 04 — NLP Classification with Transformers — **8.0**

Strong: six-run ladder 0.10 → 0.902 macro-F1, hand-written training loops, bit-exact determinism, seed study (0.8910 ± 0.0042), documented val→test non-transfer.
Improvements:

- Close the loop on the documented gap: the full-data GPU path shows 0.927 at 20k evidence — either rent a few GPU hours and publish the full-data number, or state a decision not to.
- Add error analysis: per-class confusion narrative + top misclassified examples.
Visualizations: training-curve panel per run in the ladder; per-class F1 bar chart; confidence histogram + reliability diagram (calibration is already computed — show it).

### 05 — Churn Modeling with sklearn Pipelines — **8.0**

Strong: cost-aware HPO optimizing the deployment objective (cost 282, bootstrap CI significant), isotonic calibration −95% ECE, pipeline-embedded preprocessing (no leakage).
Improvements:

- Synthetic data caps credibility — the "CRM-extract onboarding" hook exists; run one public real churn dataset (e.g., the telco set already in the data registry) end-to-end and report the transfer honestly, as 02 did with UCI.
- Add decision-curve analysis (net benefit vs threshold) — a stronger business story than ECE alone.
Visualizations: cost-vs-threshold curve with bootstrap CI band; lift/gains chart; SHAP summary for the winning pipeline.

### 06 — Routing Optimization (VRPTW) — **8.5**

Strong: ALNS at 4.23% mean gap vs published best-known across all 56 Solomon instances, 56/56 vs tuned 2-opt, randomized floor at 317%, per-family gaps. This is the most externally-verifiable project (published benchmarks).
Improvements:

- Submit the per-instance results table as a reproducible artifact anyone can diff against CVRPLIB — one command, one CSV.
- Consider one modern metaheuristic baseline (e.g., a small HGS-style run) to show where ALNS sits vs state of the art, not just vs 2-opt.
Visualizations: per-instance gap bar chart grouped by Solomon family (already partly there); convergence traces faceted by family; a route-map animation of the best solution per instance.

### 07 — Urban Mobility Demand Intelligence — **9.0** (flagship)

Strong: 41.2M real trips, lazy Polars ETL at GB scale, GBM −28.4% vs naive, p90 band at 90.8% coverage with N/A zones flagged, honest "weather ≈ 0 for point MAE" finding, live forecast endpoint in the API, green-taxi transfer study.
Improvements:

- The causal-weather question is the natural next step and is on the platform's own gap list — even a simple event-study around storms would upgrade the weather story from "importance ≈ 0" to actionable.
- Add geopandas-based choropleths (own roadmap item) — the current PNG map is static.
Visualizations: interactive zone choropleth with time slider; demand heatmap (hour × day-of-week) per borough; weather-elasticity event-study plot; coverage map showing which zones meet the p90 SLO.

### 08 — LLM Inference & Serving — **7.5**

Strong: real benchmark harness (760 requests, 19 cells, zero failures), llama.cpp vs MLX comparison, quant-vs-quality panel, concurrency sweep. Model names verified current (qwen3.6:35b-a3b, gemma4:31b both exist on Ollama).
Improvements:

- **Fix the root README** — it still calls this project "planned" while the docs publish full results. This is the single most visible inconsistency in the repo.
- Add a cost dimension: tokens/s → $/1M tokens at local electricity + amortized hardware, and vs API pricing. That's the decision a client actually makes.
- Disambiguate the runner comparison (you note quant is confounded — add one same-quant cross-runner cell to deconfound).
Visualizations: latency-throughput curves per model at c=1/4/8 (Pareto frontier); quality-vs-quant scatter with same-runner links; cost-per-token comparison table-chart vs hosted APIs.

### 09 — Agentic Workflows — **7.0**

Strong: typed pydantic-graph Plan→Execute→Critique, deterministic graders (pydantic-evals), PrefixedToolset composition, honest failure reporting (6/8 success, tool-selection 37.5%).
Improvements:

- Tool-selection accuracy of 37.5% is the honest headline — now run the improvement iteration: constrained tool subsets per task category, then re-measure. A before/after on a real weakness is the best seniority signal available.
- Run the full 14-task suite once (bounded to 8 for time) and publish both.
- Add one human-in-the-loop checkpoint demo end-to-end (it's in the architecture, not in the results).
Visualizations: per-task waterfall (where steps/time/tokens go); tool-selection confusion matrix; before/after improvement delta chart.

---

## 5. Cross-cutting recommendations

**Quick wins (days):**

1. Fix README staleness: 08 status, add 08/09 to the projects table, align "7/8/9 showcases" counts everywhere.
2. Delete or complete the 3 empty repos; archive or clean `llamaindex_query_engine_agent`.
3. Create the `amm-ds/amm-ds` profile README; add bio, email, site link.
4. **Deploy the showcase app publicly** (Fly.io/Render/Railway free tier with the mock provider). "make docker-up → localhost" filters out 95% of non-technical evaluators; a URL doesn't.
5. Decide on the commissioning brief: either remove `docs/repository_setup_report_senior_data_scientist.md`, or reframe it as an explicit, dated "built with AI-assisted development, audited by me" statement. The current middle ground (a brief addressed to a coding agent, filed as a historical record) is the worst option — discoverable, but unexplained.

**Structural (weeks):**

6. External validation: contribute to 2–3 OSS projects in the stack (pydantic-ai, DVC, scikit-learn), answer issues, or publish one project as a standalone tool. Stars/followers you earn beat stars you don't have.
7. DVC remote storage (S3/GDrive/DagsHub free tier) so `dvc pull` works, not just `dvc repro`.
8. Raise the projects/apps coverage floor from 55% toward 75%, and split the oversized modules (`evaluate.py`, `reporting.py`, `cli.py`).
9. Write 2–3 short posts (dev.to/Medium/LinkedIn) linking the case studies — the content is already written; distribution is the missing step.

---

## 6. Proposed new projects (fills genuine gaps)

| Project | Why it strengthens the portfolio | Effort |
| --- | --- | --- |
| **10 — Causal inference & experimentation** (A/B test design, power analysis, uplift modeling on a public dataset, e.g., Criteo uplift) | The platform already flags causal as a gap; experimentation is the most-requested senior DS skill and completely absent | M |
| **11 — Streaming / real-time ML** (Redpanda/Kafka + online scoring + drift monitor with live dashboard; could reuse 07's demand data replayed as a stream) | Every current project is batch; runbooks mention drift response but nothing demonstrates it live | M–L |
| **12 — LLM fine-tuning with eval** (LoRA/QLoRA on a small open model for a narrow task, with before/after eval harness reusing `portfolio-eval`) | 01/08/09 show LLM *use*; nothing shows model *adaptation* — the most common client ask after RAG | M |
| **13 — Recommender system** (implicit feedback, matrix factorization vs two-tower, ranking metrics) | Classic domain, absent here; pairs well with 04's PyTorch loop style | M |
| **14 — Geospatial ML extension of 07** (geopandas choropleths, spatial lag features, Kriging-style interpolation) | On the platform's own roadmap; upgrades a flagship instead of adding surface area | S–M |
| **Extract `portfolio-eval` as a standalone OSS package** (pip-installable eval harness with docs) | Converts internal tooling into external validation; the highest-leverage "new project" available | S–M |

Recommended sequencing: quick wins 1–5 first (they protect the credibility of everything else), then project 10 (causal) and the `portfolio-eval` extraction, then 11 or 12 depending on target clients.

---

## 7. Bottom line

As engineering, this portfolio already clears the bar it sets for itself: documented decisions, reproducible pipelines, honest evaluation. The risk is not that a reviewer finds bad code — it's that they find **a 4-day commit history, an AI commissioning brief, three empty repos, and no way to contact or click anything**, and conclude the seniority is borrowed. The fixes above are mostly cheap. Do the quick wins, deploy the app, get one external signal (OSS package or contributions), and the portfolio's substance will finally match its presentation.