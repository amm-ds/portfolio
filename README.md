# amm-ds / portfolio

[![ci](https://github.com/amm-ds/portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/amm-ds/portfolio/actions/workflows/ci.yml)

**Data Scientist & ML Engineer.** I build end-to-end systems — from data
engineering and classical ML to agentic AI — where every project ships with
its design record, reproducible pipeline, and evaluation harness.

📚 **Docs (GitHub Pages):** https://amm-ds.github.io/portfolio/ ·
🖥️ **Showcase app:** `make docker-up` → http://localhost:8000 (public deploy: `deploy/DEPLOY.md`)

## Stack

| Tool | Role | Where |
|---|---|---|
| `pydantic` (+settings) | Typed contracts at every boundary | everywhere |
| `pydantic-ai` | Agentic AI: typed tools, structured outputs, provider abstraction | 01 |
| `scikit-learn` | Classical ML: pipelines, baselines, metrics | 02, 03, 05, 07 |
| `pytorch` | Deep learning with hand-written training loops | 02, 04, 07 |
| `plotly` | The only viz library — shared theme, interactive everywhere | all |
| `dvc` | Pipelines + data versioning, reproduces from clean clone | all |
| `uv` | Single workspace monorepo, committed lockfile | root |
| `polars` | Lazy/streaming ETL over GB-scale open data | 03, 07 |
| `FastAPI` + `React/TypeScript` | Showcase API + web UI (no Streamlit) | `apps/` |

## Show it, don't just say it

Real artifacts from the pipelines (interactive versions in each [case study](https://amm-ds.github.io/portfolio/projects/)):

| Flagship demand intelligence (41.2M trips, zone map) | RAG quality-vs-cost frontier | Solver runtime-vs-gap Pareto (incl. hinted CP-SAT cross-check) |
|---|---|---|
| ![NYC taxi-zone demand map](docs/assets/readme/mobility-demand-map.png) | ![RAG quality-cost frontier](docs/assets/readme/rag-quality-cost-frontier.png) | ![Solver runtime-vs-gap Pareto](docs/assets/readme/routing-solver-pareto.png) |

## Projects

Ten projects, all working showcases on the same platform.

| # | Project | Domain | Data | Highlights |
|---|---|---|---|---|
| 01 | [RAG & Agentic AI Assistant](projects/01-rag-agent/) | Agentic AI | Wikipedia (real) | A question-answering assistant that answers only from a pinned 593-article Wikipedia corpus and cites every claim. Retrieval finds the right passage 83% of the time, but 18 of 65 hosted answers kept unsupported claims—answers are auditable, yet not trustworthy unattended.<br>Stack: pydantic-ai agent, 65-q golden set, provider A/B (local qwen3.6 vs hosted kimi, recall@5 0.831, per-phase cost metering) |
| 02 | [Hierarchical Demand Forecasting](projects/02-demand-forecasting/) | Time series | Walmart M5 + UCI Retail II (real) + synthetic | One honest protocol, two demand regimes: on dense Walmart M5 daily sales a tuned ensemble cuts forecast error to 49% vs 60% for the seasonal-naive baseline; on sparse 89%-zero retail demand the winner is the opposite—mostly-zero routing for 945 of 1,069 lumpy series.<br>Stack: rolling time-CV, statistical/GBM ensembles, sparse-demand routing, reconciliation |
| 03 | [Anomaly Detection over Telemetry](projects/03-anomaly-detection/) | Unsupervised ML | NAB (real) + seeded synthetic CI path | On NAB at a fixed 2% alert budget, IsolationForest catches 16 of 17 labelled incident windows but fires 1,609 alerts. Deduplication plus a one-page-per-day cap cuts that to 80 pages at modest recall cost—page the alert stream, not the detector score.<br>Stack: event-based metrics (PR-AUC, range-F1), detector HPO, threshold sweeps |
| 04 | [NLP Classification with Transformers](projects/04-nlp-classification/) | Deep learning NLP | AG News 120k (real) | News sorter for AG News' four topics: a language model trained on all 120k articles scores 95% macro-F1 on a fresh holdout, vs 88% for a keyword model 40x faster and free; routing doubtful items to it keeps that quality while 3 of 4 items ride at keyword cost. License unknown.<br>Stack: hand-written fine-tuning loop, macro-F1 0.946, calibration analysis |
| 05 | [Churn Modeling, sklearn Pipelines](projects/05-ml-pipeline-churn/) | Classical ML | IBM telco churn (real) + synthetic | A churn scorer on real IBM telco data (7,043 customers): serving the calibrated model at a 0.175 threshold cuts decision cost 42% (601 vs 1,035 for contacting everyone; 95% bootstrap interval -485 to -343). The cutoff must be re-derived when a missed churner's price changes.<br>Stack: pipeline-embedded preprocessing, cost-aware HPO, fairness slices |
| 06 | [Routing Optimization (VRPTW)](projects/06-routing-optimization/) | Combinatorial optimization | CVRPLIB Solomon (real benchmark) | Routing planner for the 56 standard Solomon 100-customer problems with time windows. A hand-written search returns feasible plans within 4.2% of best-known routes in ~1 second each, using 3.7 more vehicles than best-known on average; an exact solver certifies small cases only.<br>Stack: hand-written ALNS vs best-known solutions, dual distance + vehicle gap |
| 07 | [Urban Mobility Demand Intelligence](projects/07-open-data-mobility/) | Data engineering + ML | NYC TLC + NOAA (real, GB-scale) | Next-hour NYC taxi demand by zone, built on 41.2M real 2024 yellow-taxi trips and public weather: on a strict Oct-Dec holdout the model was 28% more accurate than same-hour-yesterday; its 90% upper band reached 91% coverage (sparse zones excepted).<br>Stack: lazy Polars ETL, zone-demand forecasting, weather elasticity, choropleths |
| 08 | [LLM Inference & Serving](projects/08-inference-serving/) | AI infrastructure | Local Ollama stack (real serving target) | One laptop, one run: five LLM serving setups, 760 requests, zero failures. A 4-bit mixture-of-experts model answers in 0.81 s per request at about $0.12 per 1M output tokens (electricity only). The reusable asset is the harness for re-measuring any stack on target hardware.<br>Stack: latency percentiles vs concurrency, GGUF-vs-MLX engine panel, quantization frontier |
| 09 | [Agentic Workflows](projects/09-agentic-workflows/) | Agentic AI | Synthetic 12-doc "Atlas Valley" handbook + read-only Wikipedia slice from 01 (CC BY-SA) | An auditable plan-act-review AI workflow with fixed tools and budgets passed all automated checks: 15/15 fixed tasks, 13/13 unseen answers, 5/6 should-fail probes, ~$0.13 per suite. Ready for supervised pilots, not unattended use. Data: synthetic handbook, real Wikipedia chunks.<br>Stack: pydantic-graph Plan→Execute→Critique, HITL checkpoints, budget-capped offline graders |
| 10 | [Uplift & Experimentation](projects/10-uplift-experimentation/) | Decision science | Hillstrom email RCT (real) | On 64,000-customer randomized email data, uplift targeting beat random targeting by +$2,812 (+69%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email, mailing everyone still wins. Targeting pays when sending is costly. Data: Hillstrom MineThatData, March 2008.<br>Stack: CUPED, power analysis, T/X-learner uplift, Qini & profit curves |

Flagships (01, 07) are complete end-to-end; the rest are working showcases
built on the same platform, designed for deepening.

## Selected results

<!-- RESULTS:FILLED:QA — generated from projects' reports/metrics.json at release time -->

| Project | Result |
|---|---|
| 01 RAG agent | A question-answering assistant that answers only from a pinned 593-article Wikipedia corpus and cites every claim. Retrieval finds the right passage 83% of the time, but 18 of 65 hosted answers kept unsupported claims—answers are auditable, yet not trustworthy unattended.<br>Measured: Retrieval config by measurement: recall@5 **0.831 vs 0.031 random** (65-question golden set); verify loop cut unsupported claims **60%→47%** locally and holds at **28% (18/65) on a hosted model**, RAGAS faithfulness **0.685 [0.61, 0.76]** vs 0.606 local; all four LLM phases metered — the full 65-question run cost **$3.58 cloud-equivalent** (agent $1.79 / RAGAS $1.13 / verify $0.47 / judge $0.19) under a hard $3 cap that stopped a runaway mid-run |
| 02 Forecasting | One honest protocol, two demand regimes: on dense Walmart M5 daily sales a tuned ensemble cuts forecast error to 49% vs 60% for the seasonal-naive baseline; on sparse 89%-zero retail demand the winner is the opposite—mostly-zero routing for 945 of 1,069 lumpy series.<br>Measured: Real-data primary (Walmart M5, 600 series): selection-fitted ensemble **WAPE 0.491 vs 0.603 seasonal naive** on the frozen 28-day test, gap **−0.1125 [−0.1228, −0.1026]**, with wins in both volume classes; UCI Retail II remains the sparse secondary study, using conservative selective routing rather than a universal model |
| 03 Anomaly detection | On NAB at a fixed 2% alert budget, IsolationForest catches 16 of 17 labelled incident windows but fires 1,609 alerts. Deduplication plus a one-page-per-day cap cuts that to 80 pages at modest recall cost—page the alert stream, not the detector score.<br>Measured: Real-data primary (NAB, event-based): **PR-AUC 0.527, range-F1 0.157** — the synthetic headline (ROC-AUC 0.916) was the pipeline check, and this repo says so; a detector × feature sweep finds no family winner (PR-AUC 0.515–0.574), and episode dedup + a 24 h page cap cut alerts **1,609 → 80** while *raising* range-F1 **0.157 → 0.315**; the (budget, cooldown) operating point is now tuned train-side per family — IsolationForest adopts (0.5%, 24 h) and transfers (**80 → 46 pages, range-F1 0.315 → 0.382**), LOF keeps the default, and OCSVM's marginal adoption fails to transfer (−0.043/+0.033) — the measured limit of 6-window validation evidence |
| 04 NLP | News sorter for AG News' four topics: a language model trained on all 120k articles scores 95% macro-F1 on a fresh holdout, vs 88% for a keyword model 40x faster and free; routing doubtful items to it keeps that quality while 3 of 4 items ride at keyword cost. License unknown.<br>Measured: Ladder to a full 120k fine-tune: test macro-F1 **0.9460** (naive 0.10 → TF-IDF 0.87 → bounded fine-tune 0.902 → full 0.9460 on Apple-Silicon MPS); val→test non-transfer and the Business/Sci-Tech labeling floor documented; a controlled same-device scale ladder separates device noise (same-rows CPU/MPS twins ≤0.011 macro-F1) from the data effect (**+1.3–1.6 pp per 3× rows**, 3.6k→108k, reproducing on a fresh holdout) |
| 05 Churn | A churn scorer on real IBM telco data (7,043 customers): serving the calibrated model at a 0.175 threshold cuts decision cost 42% (601 vs 1,035 for contacting everyone; 95% bootstrap interval -485 to -343). The cutoff must be re-derived when a missed churner's price changes.<br>Measured: Real-data primary (IBM telco): cost-aware HPO selects XGBoost; business cost **1,035 → 601 (−41.9%)**, paired bootstrap CI **[−485, −343]**; isotonic improves both ECE and the cost optimum at FN=5 (619 → 601) — the synthetic conclusion did not transfer, and the cutoff itself moves with the missed-churner price (t\*=0.200/0.175/0.100 at FN=3/5/8, every CI excludes zero) |
| 06 VRPTW | Routing planner for the 56 standard Solomon 100-customer problems with time windows. A hand-written search returns feasible plans within 4.2% of best-known routes in ~1 second each, using 3.7 more vehicles than best-known on average; an exact solver certifies small cases only.<br>Measured: Hand-written ALNS: **4.23% mean distance gap vs best-known across all 56 Solomon instances** (+3.73 mean vehicles — both criteria reported; vehicles-first ranking: ALNS 38/56, fleet-first variant 5/56); the hinted CP-SAT cross-check could not improve any incumbent, and an unhinted CP-SAT at the same 10 s budget produced no feasible plan on any instance |
| 07 Mobility | Next-hour NYC taxi demand by zone, built on 41.2M real 2024 yellow-taxi trips and public weather: on a strict Oct-Dec holdout the model was 28% more accurate than same-hour-yesterday; its 90% upper band reached 91% coverage (sparse zones excepted).<br>Measured: Zone-hour demand over 41.2M trips: served `gbm_tuned` MAE **4.676 (−28.3% vs same-hour-yesterday persistence, MASE 0.763)**; **p90 band 90.8% coverage** (sparse N/A-borough zones under-cover at 84.7%); permutation importance shows weather ≈ 0 for point MAE — its value is the directional elasticity signal; the drift observatory has since scored the first genuinely unseen month (2025-01, fetched live): **MAE 4.442 vs pinned 4.676 (−5.0%, in-window)**, coverage 87.4% — three months scored, none regressed; per-service retraining is productionized — the green-taxi bundle (`gbm_green_served`, 534k zone-hours) serves behind the API's optional `service` field |
| 08 Inference | One laptop, one run: five LLM serving setups, 760 requests, zero failures. A 4-bit mixture-of-experts model answers in 0.81 s per request at about $0.12 per 1M output tokens (electricity only). The reusable asset is the harness for re-measuring any stack on target hardware.<br>Measured: Local serving benchmark (author run): 19 cells / 760 requests / 0 failures; **MLX ≈ 2.9× GGUF tok/s on Apple Silicon**; 4-bit quantization costs serving headroom, not structured-output validity |
| 09 Agentic | An auditable plan-act-review AI workflow with fixed tools and budgets passed all automated checks: 15/15 fixed tasks, 13/13 unseen answers, 5/6 should-fail probes, ~$0.13 per suite. Ready for supervised pilots, not unattended use. Data: synthetic handbook, real Wikipedia chunks.<br>Measured: Full 15-task hosted run on `kimi-for-coding` (per-call tool capture): **15/15 on every grader** — answer success, exact tool set (up from 8/15: per-call traces located the unplanned calls, prompt/docstring surgery removed them), step budget, latency budget (median **18.2 s**/task, p95 31.1 s vs the 60 s cap); sealed held-out set, expanded to **19 tasks** (2026-10-30): **13/13 answers with exact tool sets, 5/6 should-fail refusals** — the miss is a failure-message wording gap, not confabulation; the h11–h19 wave ran on local Ollama at **$0.00 metered** and exposed the hosted-tuned 60 s budget as provider-sensitive (7/9 local tasks exceed it); suite cost **$0.13 cloud-equivalent** of the $2.00 suite cap (~$0.0088/task), with two repeat passes confirming 15/15 answers and exact tool sets at ~$0.10–0.15 per suite; t15 retrieves two-article facts from 01's real Wikipedia index |
| 10 Uplift | On 64,000-customer randomized email data, uplift targeting beat random targeting by +$2,812 (+69%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email, mailing everyone still wins. Targeting pays when sending is costly. Data: Hillstrom MineThatData, March 2008.<br>Measured: Hillstrom RCT: ATE +0.68pp, CUPED covariate lesson, power analysis; T-learner **+$2,812/wave vs random** at 25% budget (own paired CI [+$718, +$4,767] — established); **mail-everyone ($16,103) beats it at $0.01/email** (paired CI [−$13,125, −$5,808] below zero) — the value is concentration (~42% of conversions at ¼ volume); targeting wins above ≈$0.30/email (break-even grid); Qini curve-area ranking not established (spans zero; the paired response−T profit CI [−$3,617, −$48] is what favors T) |

## Engineering practices

- **Architecture decision records** for every platform-level choice
  ([ADRs](docs/architecture/adr/)) and a [reference architecture](docs/architecture/platform.md).
- **Contracts:** pydantic models at every boundary; hypothesis property tests on
  validators; mypy strict on shared libs.
- **Reproducibility:** committed `uv.lock`; `dvc repro` per project; dataset
  cards pin URLs + checksums in [data-registry/](docs/data-registry/).
- **Operability:** SLOs in design docs, runbooks for drift / LLM cost /
  pipeline restore ([docs/runbooks/](docs/runbooks/)).
- **Review culture:** PR template with design questions, engineering playbook
  ([docs/engineering-playbook.md](docs/engineering-playbook.md)).

## Live endpoints

The showcase app serves the pipelines' real artifacts over HTTP. Run
`make docker-up` → http://localhost:8000:

- `POST /projects/07-open-data-mobility/forecast` — zone-hour demand with a p90 band (07; optional `service: "yellow"|"green"` routes the per-service bundle, default yellow)
- `POST /projects/02-demand-forecasting/forecast` — hierarchical demand forecast (02)
- `POST /projects/05-ml-pipeline-churn/score` — churn propensity scoring (05)
- `POST /projects/06-routing-optimization/solve` — VRPTW routing solver (06)
- Per-project story / metrics / figure APIs: `GET /projects/{id}/{story,metrics,figures}`
- Opt-in RAG chat API: `POST /rag/chat` (streaming variant included), disabled by default

The 02/05/07 serving bundles are committed and cached after their first load;
06 is computed from the request. If artifacts are absent, their endpoints
return **503** with rebuild instructions. Reproduce a pipeline from its project
directory, for example `cd projects/02-demand-forecasting && uv run dvc repro`.
The standard image deliberately contains neither the RAG package nor its
retrieval index; see [deployment](deploy/DEPLOY.md) before enabling chat.

For the single-container public deploy, set the required `DOMAIN` and
`IP_HASH_SALT`, then follow the exact `IMAGE`/`TAG` build/run flow in
[deploy/DEPLOY.md](deploy/DEPLOY.md). Caddy provisions TLS and waits for API
readiness. The docs site is always live: https://amm-ds.github.io/portfolio/

## Reproduce in 3 commands

```bash
git clone https://github.com/amm-ds/portfolio.git && cd portfolio
make setup     # uv sync + pre-commit
cd projects/02-demand-forecasting && uv run dvc repro  # or choose another project
```

…or open in GitHub Codespaces (`.devcontainer/`) — the environment builds itself.

The ordinary showcase endpoints need no LLM key. RAG chat is disabled by
default and there is no production mock provider; a deliberately enabled local
Project 01 uses Ollama unless `LLM_BASE_URL`/`LLM_API_KEY` configure a hosted
provider (see [.env.example](.env.example)).

## Services & engagement

Freelance ML/AI engineering across seven offerings — AI/LLM systems,
machine learning, optimization, data engineering, MLOps, interactive
dashboards, and full-stack product engineering. Fixed-scope pilots,
retainers, advisory. Full details:
[Services](docs/site/services.md) · every project above is a live case study
(background → objectives → data → EDA → training → evaluation → results →
conclusions, each with a naive baseline and the honest delta).

## Contact & availability

- **Start an engagement:** [open an inquiry](https://github.com/amm-ds/portfolio/issues/new?title=Inquiry%3A%20&body=%2A%2AContext%2A%2A%3A%20) —
  discovery call first, written scope after (details on the
  [Services page](https://amm-ds.github.io/portfolio/site/contact/)).
- GitHub: [@amm-ds](https://github.com/amm-ds)
- Languages: English, Spanish.

MIT licensed. Datasets carry their own licenses — see the dataset cards.
Security vulnerabilities: [SECURITY.md](SECURITY.md) — never open a public
issue for them.
