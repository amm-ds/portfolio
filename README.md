# amm-ds / portfolio

**Data Scientist & ML Engineer.**
End-to-end systems from data engineering and classical ML to agentic AI: every
project ships with its design record, reproducible pipeline, and evaluation
harness.

📚 **Docs (GitHub Pages):** https://amm-ds.github.io/portfolio/ ·
🖥️ **Showcase app:** `make docker-up` → http://localhost:8000

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

Nine projects, all working showcases on the same platform.

| # | Project | Domain | Data | Highlights |
|---|---|---|---|---|
| 01 | [RAG & Agentic AI Assistant](projects/01-rag-agent/) | Agentic AI | Wikipedia (real) | pydantic-ai agent, typed tools, citation-enforced outputs, 65-question golden set, chunk-size sweep |
| 02 | [Hierarchical Demand Forecasting](projects/02-demand-forecasting/) | Time series | UCI Online Retail II (real) + synthetic | Leakage-proof time-CV, LightGBM vs PyTorch vs ETS, reconciliation |
| 03 | [Anomaly Detection over Telemetry](projects/03-anomaly-detection/) | Unsupervised ML | NAB (real) + seeded synthetic CI path | Event-based metrics (PR-AUC, range-F1), detector HPO, threshold sweeps |
| 04 | [NLP Classification with Transformers](projects/04-nlp-classification/) | Deep learning NLP | AG News 120k (real) | Hand-written fine-tuning loop, macro-F1 0.946, calibration analysis |
| 05 | [Churn Modeling, sklearn Pipelines](projects/05-ml-pipeline-churn/) | Classical ML | IBM telco churn (real) + synthetic | Pipeline-embedded preprocessing, cost-aware HPO, fairness slices |
| 06 | [Routing Optimization (VRPTW)](projects/06-routing-optimization/) | Combinatorial optimization | CVRPLIB Solomon (real benchmark) | Hand-written ALNS vs best-known solutions, dual distance + vehicle gap |
| 07 | [Urban Mobility Demand Intelligence](projects/07-open-data-mobility/) | Data engineering + ML | NYC TLC + NOAA (real, GB-scale) | Lazy Polars ETL, zone-demand forecasting, weather elasticity, choropleths |
| 08 | [LLM Inference & Serving](projects/08-inference-serving/) | AI infrastructure | Local Ollama stack (real serving target) | Latency percentiles vs concurrency, GGUF-vs-MLX engine panel, quantization frontier |
| 09 | [Agentic Workflows](projects/09-agentic-workflows/) | Agentic AI | 15-task suite (14 synthetic + real Wikipedia retrieval via 01's index) | pydantic-graph Plan→Execute→Critique, HITL checkpoints, budget-capped offline graders |
| 10 | [Uplift & Experimentation](projects/10-uplift-experimentation/) | Decision science | Hillstrom email RCT (real) | CUPED, power analysis, T/X-learner uplift, Qini & profit curves |

Flagships (01, 07) are complete end-to-end; the rest are working showcases
built on the same platform, designed for deepening.

## Selected results

<!-- RESULTS:FILLED:QA — generated from projects' reports/metrics.json at release time -->

| Project | Result |
|---|---|
| 01 RAG agent | Retrieval config by measurement: recall@5 **0.831 vs 0.031 random on the 65-question golden set** (earlier 26-q sweep: 0.962); chosen MiniLM/chunk-200/top_k-3/rerank cuts context cost **−65%** at equal recall; verify loop A/B: unsupported claims **18→14**, correct **12→15** (n=30) at 33 repair calls, RAGAS faithfulness 0.651→0.606 (judge noise) — grounding improved, with its repair-call cost measured |
| 02 Forecasting | Real-data primary (UCI Online Retail II): **hgb_tuned MAE 8.989 — the only model with MASE < 1** on intermittent real demand; the synthetic champion (lgbm_tuned 8.413, −41.9% vs persistence) drops to fourth there — tuned configs do not transfer across regimes |
| 03 Anomaly detection | Real-data primary (NAB, event-based): **PR-AUC 0.527, range-F1 0.157** — the synthetic headline (ROC-AUC 0.916) was the pipeline check, and this repo says so; seeded synthetic stays as the CI fast path |
| 04 NLP | Ladder to a full 120k fine-tune: test macro-F1 **0.9460** (naive 0.10 → TF-IDF 0.87 → bounded fine-tune 0.902 → full 0.9460 on Apple-Silicon MPS); val→test non-transfer and the Business/Sci-Tech labeling floor documented |
| 05 Churn | Real-data primary (IBM telco): cost-aware HPO selects XGBoost; business cost **1,035 → 601 (−41.9%)**, paired bootstrap CI **[−485, −343]**; isotonic improves both ECE and the cost optimum on real data — the synthetic conclusion did not transfer |
| 06 VRPTW | Hand-written ALNS: **4.23% mean distance gap vs best-known across all 56 Solomon instances** (+3.73 mean vehicles — both criteria reported; vehicles-first ranking 43/56); the hinted CP-SAT cross-check could not improve any incumbent |
| 07 Mobility | Zone-hour demand over 41.2M trips: GBM MAE 4.67 (−28.4% vs naive); **p90 band 90.8% coverage** (N/A zones flagged); permutation importance shows weather ≈ 0 for point MAE — its value is the elasticity signal |
| 08 Inference | Local serving benchmark (author run): 19 cells / 760 requests / 0 failures; **MLX ≈ 2.9× GGUF tok/s on Apple Silicon**; 4-bit quantization costs serving headroom, not structured-output validity |
| 09 Agentic | Full 15-task hosted run on `kimi-for-coding` (thinking disabled, ~9.5 min suite): answer success **15/15**, step budget 15/15, latency budget 14/15, median **19.9 s**/task; tool-selection **3/15** under exact-set grading (unprompted extra tools on correct answers); ledger **$0.13** of the $2.00 suite cap; t15 retrieves two-article facts from 01's real Wikipedia index |
| 10 Uplift | Hillstrom RCT: ATE +0.68pp, CUPED covariate lesson, power analysis; T-learner **+$2,812/wave vs random** at 25% budget (paired CI [−$3,617, −$48] — established), while **mail-everyone ($16,103) beats it at $0.01/email** — the value is concentration (~42% of conversions at ¼ volume); targeting wins above ≈$0.30/email (break-even grid); Qini curve-area ranking reported as not established (CI spans zero) |

## Engineering practices

- **Architecture decision records** for every platform-level choice
  ([architecture/](architecture/adr/)) and a [reference architecture](architecture/platform.md).
- **Contracts:** pydantic models at every boundary; hypothesis property tests on
  validators; mypy strict on shared libs.
- **Reproducibility:** committed `uv.lock`; `dvc repro` per project; dataset
  cards pin URLs + checksums in [data-registry/](data-registry/).
- **Operability:** SLOs in design docs, runbooks for drift / LLM cost /
  pipeline restore ([docs/runbooks/](docs/runbooks/)).
- **Review culture:** PR template with design questions, engineering playbook
  ([docs/engineering-playbook.md](docs/engineering-playbook.md)).

## Live demo

The showcase app runs locally via `make docker-up`; the public deployment link lands
here once the Hetzner host is live (see `deploy/DEPLOY.md`). The docs site is always
available: https://amm-ds.github.io/portfolio/

## Reproduce in 3 commands

```bash
git clone https://github.com/amm-ds/portfolio.git && cd portfolio
make setup     # uv sync + pre-commit
dvc repro      # downloads pinned public data, runs all pipelines
```

The showcase app runs without an LLM key (deterministic mock provider); set
`LLM_BASE_URL`/`LLM_API_KEY` in `.env` for a live provider (see
[.env.example](.env.example)).

## Services & engagement

Freelance ML/AI engineering — systems delivery, agentic AI/RAG, data
engineering, forecasting & analytics, MLOps/reproducibility audits.
Fixed-scope pilots, retainers, advisory. Full details:
[Services](docs/site/services.md) · every project above is a live case study
(background → objectives → data → EDA → training → evaluation → results →
conclusions, each with a naive baseline and the honest delta).

## Contact & availability

- GitHub: [@amm-ds](https://github.com/amm-ds)
- Freelance/consulting: open to engagements — details on the
  [About/Services page](https://amm-ds.github.io/portfolio/site/about/).
- Languages: English, Spanish.

MIT licensed. Datasets carry their own licenses — see the dataset cards.
