# amm-ds / portfolio

**Senior Data Scientist & ML/AI Engineer — architect-level portfolio.**
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

## Projects

| # | Project | Domain | Data | Highlights |
|---|---|---|---|---|
| 01 | [RAG & Agentic AI Assistant](projects/01-rag-agent/) | Agentic AI | Wikipedia (real) | pydantic-ai agent, typed tools, citation-enforced outputs, faithfulness eval, chunk-size sweep |
| 02 | [Hierarchical Demand Forecasting](projects/02-demand-forecasting/) | Time series | Synthetic (+ UCI opt.) | Leakage-proof time-CV, GBM vs PyTorch, reconciliation |
| 03 | [Anomaly Detection over Telemetry](projects/03-anomaly-detection/) | Unsupervised ML | Synthetic (+ NSL-KDD opt.) | DQ gates, IsolationForest vs LOF vs OneClassSVM |
| 04 | [NLP Classification with Transformers](projects/04-nlp-classification/) | Deep learning NLP | AG News (real) | Hand-written fine-tuning loop, macro-F1, confusion matrices |
| 05 | [Churn Modeling, sklearn Pipelines](projects/05-ml-pipeline-churn/) | Classical ML | Synthetic (messy) | Pipeline-embedded preprocessing, calibration, business-cost thresholds |
| 06 | [Routing Optimization (VRPTW)](projects/06-routing-optimization/) | Combinatorial optimization | CVRPLIB Solomon (real benchmark) | Savings + 2-opt vs published optima, gap-% table |
| 07 | [Urban Mobility Demand Intelligence](projects/07-open-data-mobility/) | Data engineering + ML | NYC TLC + NOAA (real, GB-scale) | Lazy Polars ETL, zone-demand forecasting, weather elasticity, choropleths |

Flagships (01, 07) are complete end-to-end; 02–06 are working showcases built
on the same platform, designed for deepening.

## Selected results

<!-- RESULTS:FILLED:QA — generated from projects' reports/metrics.json at release time -->

| Project | Result |
|---|---|
| 01 RAG agent | Retrieval recall@5 **0.962 vs 0.038 random** (+0.92) on a 593-article Wikipedia corpus; chunk-size sweep; p95 3.6 ms offline floor; est. live cost ≈ $0.0004/query |
| 02 Forecasting | Gradient boosting MAE 8.62 — **−40.5% vs persistence naive** (Ridge 9.12, −37.0%), leakage-proof time-CV, stable 38.8–41.1% gain every fold |
| 03 Anomaly detection | IsolationForest ROC-AUC **0.916 vs 0.509 random** (+0.41; PR 6.5× prevalence floor); honest analysis of why LOF/OneClassSVM fail on clustered anomalies |
| 04 NLP | DistilBERT macro-F1 **0.902 vs 0.253 random / 0.100 majority** (+64.9 pp; TF-IDF 0.871), hand-written PyTorch loop, bounded reproducible split |
| 05 Churn | Threshold-tuned pipeline: business cost **−35.9% vs naive majority** (threshold tuning alone −19.4%), ROC-AUC 0.834, calibration + permutation-importance reports |
| 06 VRPTW | 2-opt **19.6% mean gap vs published Solomon optima** — from 303% (randomized) → 24.6% (savings) → 19.6%; 10 real benchmark instances, honest fleet-cap caveats |
| 07 Mobility | Zone-hour demand over 41.2M real trips: GBM MAE 4.67 (**−28.4% vs naive lag-24**), p90 band 91.1% coverage, per-borough weather elasticity |

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
