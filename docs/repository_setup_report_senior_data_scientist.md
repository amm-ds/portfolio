# Repository Setup Report — Principal/Architect-Level Data Science & AI Portfolio

**Prepared for:** Alejandro Mérida Maroto (amm-ds)
**Purpose:** Brief for a coding agent to scaffold a public GitHub repository that functions as (1) a client-facing portfolio for freelance engagements and (2) a demonstration of principal/architect-level engineering judgment — not just working models, but documented decisions, reference architectures, and reproducible platforms.
**Mandated base stack:** `pydantic`, `pydantic-ai`, `scikit-learn`, `plotly`, `dvc`, `uv`, `pytorch`

---

## 1. Objectives & Positioning

The repository must do three jobs simultaneously:

1. **Client-facing portfolio** — a technical evaluator at a prospective client should be able to judge seniority within 5 minutes of landing on the repo. Seniority here is proven by *engineering artifacts around the code* (decision records, architecture docs, SLOs, runbooks), not by code volume.
2. **Proof of the mandated stack** — every project visibly uses pydantic (typed contracts), pydantic-ai (agentic AI), scikit-learn (classical ML), plotly (interactive visualization), DVC (data/model versioning), uv (packaging), PyTorch (deep learning).
3. **Extendable platform** — a monorepo structured like an internal platform: shared libraries, documented extension points, ADRs explaining why things are the way they are. A new showcase project should be addable in hours, not days.

**Positioning statement (README hero, no fluff):**
> Senior Data Scientist & ML/AI Engineer — end-to-end systems from data engineering and classical ML to agentic AI. Architect-level portfolio: every project ships with its design record, reproducible pipeline, and evaluation harness.

**The principal/architect bar — what distinguishes this repo from a mid-level portfolio:**

| Artifact | Where | What it proves |
|---|---|---|
| Architecture Decision Records (ADRs) | `architecture/adr/` | Trade-off reasoning, not just outcomes |
| Reference architecture doc | `architecture/platform.md` | System-level thinking across projects |
| Per-project design docs with diagrams | `docs/projects/` | Requirements → design → evaluation chain |
| SLOs, cost & latency budgets | Agent project docs | Production mindset for LLM systems |
| Runbooks | `docs/runbooks/` | Operability (drift, incident, rollback) |
| Engineering playbook | `CONTRIBUTING.md` | How a team would be run |
| Review standards & PR template | `.github/` | Technical-leadership culture |
| Reproducibility contract | Root README | `uv sync && dvc repro` from clean clone |

---

## 2. Repository Identity

- **Name:** `amm-ds/portfolio` (alternative: `amm-ml-platform`). Public visibility.
- **Default branch:** `main`. **License:** MIT.
- **GitHub repo topics:** `machine-learning`, `data-science`, `data-engineering`, `agentic-ai`, `llm`, `rag`, `pytorch`, `scikit-learn`, `pydantic`, `dvc`, `uv`, `plotly`, `mlops`, `time-series`, `anomaly-detection`, `optimization`.

---

## 3. Technology Stack (pinned roles)

| Role | Tool | Mandatory usage pattern |
|---|---|---|
| Packaging / env | **uv** | Single workspace root; `uv.lock` committed |
| Config & validation | **pydantic** | All configs, dataset schemas, API contracts as `BaseModel`; `pydantic-settings` for env |
| Agentic AI / LLM | **pydantic-ai** | RAG agent with structured tool calls, type-safe outputs, eval harness |
| Classical ML | **scikit-learn** | `Pipeline` + `ColumnTransformer`, custom transformers, leakage-free CV |
| DL | **pytorch** (+ torchvision, transformers) | Hand-written training loops — no high-level trainer hiding the mechanics |
| Data viz | **plotly** | All figures interactive; exported HTML embedded in docs |
| Data versioning | **dvc** | Pipelines (`prepare → train → evaluate`); datasets & model artifacts tracked, never committed raw |
| Testing | pytest, hypothesis | Unit tests everywhere; property-based tests on validators |
| Lint / format / types | ruff, mypy (strict on shared libs) | Enforced via pre-commit + CI |
| Docs | mkdocs-material, GitHub Pages, mermaid | ADRs, design docs, runbooks, embedded plotly HTML |
| CI | GitHub Actions | Lint → typecheck → test → docs deploy |

Supporting (kept minimal per project): `polars`, `numpy`, `typer`, `optuna`, `sentence-transformers`, `chromadb`/`faiss-cpu`, `datasets` (HF), `python-ortools` (optional; hand-written heuristics preferred).

**Non-goals:** no TensorFlow, no Streamlit, no cloud SDKs required to run, no API key required for CI.

---

## 4. Monorepo Architecture

```
amm-ds/portfolio
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # ruff, mypy, pytest
│   │   └── docs.yml                # mkdocs → GitHub Pages
│   ├── PULL_REQUEST_TEMPLATE.md    # includes design-question checklist
│   └── ISSUE_TEMPLATE/
├── .dvc/  .dvcignore
├── .gitignore  .pre-commit-config.yaml  LICENSE  Makefile
├── pyproject.toml                  # uv workspace root
├── uv.lock
├── README.md                       # portfolio landing page
├── architecture/
│   ├── platform.md                 # reference architecture across all projects
│   ├── adr/
│   │   ├── 0001-uv-workspace-monorepo.md
│   │   ├── 0002-pydantic-contracts-everywhere.md
│   │   ├── 0003-dvc-pipeline-reproducibility.md
│   │   ├── 0004-llm-provider-abstraction.md
│   │   └── 0005-plotly-as-only-viz.md
│   └── diagrams/                   # mermaid sources
├── docs/                           # mkdocs-material site
│   ├── index.md
│   ├── engineering-playbook.md     # standards, review culture, definition of done
│   ├── projects/01..07-*.md        # problem → design → results → run
│   └── runbooks/
│       ├── drift-response.md
│       ├── llm-cost-incident.md
│       └── pipeline-restore.md
├── libs/
│   ├── portfolio-core/             # shared contracts, config, plotting, eval, synthetic data
│   └── portfolio-eval/             # reusable evaluation harness (RAG + ML metrics, report builder)
├── projects/
│   ├── 01-rag-agent/               # agentic AI flagship
│   ├── 02-demand-forecasting/      # hierarchical TS: sklearn + pytorch
│   ├── 03-anomaly-detection/       # ETL + unsupervised ML (open dataset option)
│   ├── 04-nlp-classification/      # pytorch transformers + optuna (open dataset)
│   ├── 05-ml-pipeline-churn/       # sklearn Pipeline showcase
│   ├── 06-routing-optimization/    # VRPTW on public benchmark instances
│   └── 07-open-data-mobility/      # NEW — flagship on real open data (NYC TLC + NOAA)
└── data-registry/                  # dataset cards: source, license, checksums, access notes
    ├── nyc-tlc.md
    ├── noaa-ghcn.md
    ├── uci-online-retail-ii.md
    ├── cvrplib-solomon.md
    ├── ag-news.md
    └── nsl-kdd.md
```

**Structural rules the agent must follow:**

1. **uv workspace** — root `pyproject.toml` declares `[tool.uv.workspace] members = ["libs/*", "projects/*"]`; shared deps pinned once; `torch` only where needed (02, 04).
2. **`libs/` is mandatory and load-bearing.** Six projects duplicating config/schema/eval code would read mid-level. `portfolio-core` (contracts, config, plotting themes, synthetic generators) and `portfolio-eval` (metrics protocols, eval report builders, RAG faithfulness checks) are the platform.
3. **Identical internal layout per project:**
   ```
   projects/0X-name/
   ├── pyproject.toml
   ├── README.md              # problem, design summary, results, reproduce block
   ├── DESIGN.md              # requirements, options considered, decision, diagram (mermaid)
   ├── dvc.yaml               # stages: prepare → train → evaluate
   ├── data/                  # DVC-tracked; only .dvc files in git
   ├── src/0x_name/
   │   ├── config.py          # pydantic Settings + RunConfig
   │   ├── data.py            # load/validate via portfolio_core.schemas
   │   ├── features.py  model.py  evaluate.py  cli.py   # typer entrypoints
   ├── notebooks/             # exploratory only, cleared outputs
   └── tests/
   ```
4. **Data policy:** no raw data in git. Every external dataset gets a **dataset card** in `data-registry/` (source URL, license, size, checksum, access script, snapshot date). DVC tracks prepared artifacts; external sources are fetched by `prepare` stages and pinned by checksum in the card.
5. **No dead code, no empty scaffolds.** Every module imported somewhere; every README shows real results.

---

## 5. Project Specifications

### Project 01 — RAG & Agentic AI Assistant (flagship)
- **Stack:** pydantic-ai, sentence-transformers, chromadb/faiss, pydantic, plotly, portfolio-eval.
- **Domain:** document-analysis assistant over a public corpus — `wikimedia/wikipedia` (20231101.en subset, filtered to a fixed topic list for a bounded retrieval domain). Fully offline-reproducible snapshot.
- **Requirements:**
  - Typed agent: tools as `@agent.tool` functions with pydantic-validated args/returns; structured outputs (`Citation`, `AnalysisResult`) enforced by pydantic.
  - RAG: chunking → embeddings → vector store → re-ranking; retrieval eval harness (faithfulness, answer relevance, context recall) in `portfolio-eval`.
  - **SLOs and budgets documented in DESIGN.md**: p95 latency target, cost per query budget, fallback chain (provider-agnostic abstraction; local/mock mode so CI needs no key).
  - plotly: retrieval quality vs. chunk-size sweep; cost-vs-quality frontier.
  - `make demo` → CLI chat loop against local index.
- **DVC stages:** `prepare_corpus → build_index → evaluate_retrieval`.
- **Architect artifact:** ADR-0004 (provider abstraction) referenced from DESIGN.md.

### Project 02 — Hierarchical Demand Forecasting
- **Stack:** scikit-learn (Ridge/GBM baselines), pytorch (small temporal net, hand-written loop), plotly, optuna.
- **Data:** synthetic retail hierarchy (default, seedable) **plus optional real-data track: UCI Online Retail II** (UK e-commerce transactions, 2009–2011) — see dataset card; the `prepare` stage supports both sources behind one pydantic `DataSource` contract.
- **Requirements:** time-based CV wrapper in portfolio-core (leakage-proof); baseline vs. GBM vs. PyTorch comparison (MAE/MAPE/RMSE plotly panel); hierarchical reconciliation (bottom-up + MinT-lite); Optuna HPO with plotly history/param-importance.
- **DVC stages:** `prepare → train_baselines → train_nn → evaluate`.

### Project 03 — Anomaly Detection over Telemetry
- **Stack:** polars (ETL), scikit-learn (IsolationForest / One-Class SVM / LOF), plotly.
- **Data:** synthetic telemetry (default) **plus optional real-data track: NSL-KDD** network-intrusion benchmark (UNB Canadian Institute for Cybersecurity) — dataset card with direct download notes.
- **Requirements:** polars ETL with data-quality gates (pydantic schema validation, null-rate/range thresholds — failures halt the pipeline loudly); three detector families compared at fixed contamination with plotly ROC/PR; context/aggregate features; `dq report` CLI emitting an HTML data-quality dashboard.
- **DVC stages:** `extract → validate → detect → report`.

### Project 04 — NLP Multi-class Classification with Transformers
- **Stack:** pytorch + HF transformers/datasets, sentence-transformers, optuna, scikit-learn metrics, plotly.
- **Data:** **real open dataset — `fancyzhx/ag_news`** on Hugging Face (127k news articles, 4 classes, research use) via the `datasets` library; no manual download.
- **Requirements:** fine-tune a small transformer (distilbert-class) with a clean hand-written PyTorch loop (custom Trainer-lite); sentence-embedding + logistic-regression baseline (sklearn) vs. fine-tuned model (macro-F1, confusion matrices as plotly); Optuna Bayesian HPO with pruning; topic-modeling appendix (embeddings + clustering + 2-D scatter).
- **DVC stages:** `prepare → train → evaluate`.

### Project 05 — Churn Modeling with Production-Grade sklearn Pipelines
- **Stack:** scikit-learn (`Pipeline`, `ColumnTransformer`, custom `BaseEstimator` transformers), pydantic feature schemas, plotly.
- **Data:** synthetic telecom/e-commerce churn (mixed dtypes, deliberate messiness: outliers, missingness, drift).
- **Requirements:** all preprocessing inside sklearn `Pipeline`; tested custom transformers; calibration curves + permutation importance (plotly); threshold tuning with business-cost curve; DESIGN.md discusses why pipeline-embedded preprocessing is a deployment contract.
- **DVC stages:** `prepare → train → evaluate`.

### Project 06 — Routing Optimization on Public Benchmark Instances
- **Stack:** hand-written savings + 2-opt heuristics (ortools only as an optional comparison baseline), pydantic problem definitions, plotly.
- **Data:** **real public benchmark — CVRPLIB (PUC-Rio)** Solomon VRPTW instances (56 classic instances, 100 customers each, published optima) — dataset card with instance URLs and known-best values.
- **Requirements:** problem spec as validated pydantic models (`Order`, `Vehicle`, `RoutePlan`); naive nearest-neighbor vs. savings vs. 2-opt; results table against published optima (gap %); interactive plotly route maps.
- **DVC stages:** `prepare → optimize → evaluate`.

### Project 07 — Open-Data Flagship: Urban Mobility Demand Intelligence (NEW)
The anchor project that proves end-to-end capability on **real, messy, large public data** — the one to show clients first.

- **Data (two linked open sources, dataset cards required):**
  1. **NYC TLC Trip Records** — yellow/green taxi + FHV trips, monthly Parquet files, ~1M trips/day, published since 2009. Anonymous HTTPS download (no account). Use a bounded slice (e.g., 12 months of yellow-taxi Parquet for zones 1–263) so `dvc repro` stays laptop-friendly.
  2. **NOAA GHCN-Daily** — daily weather observations (Central Park station as the NYC join key) via NCEI direct download.
- **Stack:** polars (lazy, out-of-core Parquet ETL), pydantic (zone/trip/weather schemas + data-quality contracts), scikit-learn (demand GBM baseline + quantile regression), pytorch (temporal demand model, hand-written loop), plotly (zone-level demand heatmaps, forecast panels), DVC (multi-stage pipeline over GB-scale inputs).
- **Pipeline:** `download → validate (dq gates) → join (trips × weather × taxi zones) → features → train_baselines → train_nn → evaluate → dashboard`.
- **Deliverables:**
  - Zone-hour demand forecasting with MAE/MAPE per borough, plotly choropleth-style heatmap over taxi zones.
  - Weather-impact analysis (rain/temp elasticity of demand) — a business-facing insight section in the docs.
  - Full `dq report` and a DESIGN.md covering scale decisions (why lazy Polars, memory budget, chunking).
  - Reproduce block in README: `dvc repro` regenerates everything from public URLs; checksums pinned in the dataset cards.
- **Why this is the flagship:** real volume, real messiness, real joins — data engineering, ML, and communication of insight in one project.

---

## 6. Open Datasets Registry (verified links, October 2026)

Every external dataset ships with a card in `data-registry/` containing: canonical URL, license/terms, snapshot date, checksum, size, access method (script/CLI/HF loader), and which project consumes it.

| Dataset | Canonical source | License / terms | Size | Consumed by |
|---|---|---|---|---|
| NYC TLC Trip Records | https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page | NYC terms of use; free anonymous download, monthly Parquet | ~1M trips/day; slice 12 months | **07** |
| NOAA GHCN-Daily | https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861 (NCEI direct download) | Public domain (US Gov) | Station daily files; Central Park subset | **07** |
| UCI Online Retail II | https://archive.ics.uci.edu/dataset/502/online+retail+ii | Free for research; cite Chen et al. 2012 | ~1.07M transactions, 2009–2011 | **02** (optional track) |
| CVRPLIB — Solomon VRPTW | https://galgos.inf.puc-rio.br/cvrplib/ (VRPTW → Solomon set; includes published optima) | Academic benchmark, free | 56 instances × 100 customers | **06** |
| AG News (HF) | https://huggingface.co/datasets/fancyzhx/ag_news | Research purposes | 127k articles, 4 classes | **04** |
| NSL-KDD | https://www.unb.ca/cic/datasets/nsl.html | Research benchmark (UNB CIC) | 148,515 records, 43 features | **03** (optional track) |
| Wikipedia (HF) | https://huggingface.co/datasets/wikimedia/wikipedia (config `20231101.en`) | CC BY-SA / GFDL; attribution required — card must carry attribution note | 6.4M articles (subset used) | **01** |

**Registry rules:** snapshots are content-pinned (checksum + date in the card); the `prepare` stage fails loudly on checksum mismatch; attribution lines appear in docs for CC-licensed sources (Wikipedia).

---

## 7. Engineering Standards (non-negotiable)

1. **Type safety:** mypy strict on `libs/*`; typed everywhere; pydantic models at every cross-module boundary.
2. **Lint/format:** ruff (E, F, I, UP, B, SIM, RUF), line length 100; pre-commit enforced.
3. **Tests:** pytest + hypothesis property tests on validators; CI green required; coverage ≥80% libs, ≥60% projects.
4. **Config discipline:** zero hardcoded constants in logic; secrets only via env (`.env.example` in root).
5. **Reproducibility:** committed `uv.lock`; `dvc repro` per project; README "Reproduce in 3 commands" block; clean-clone test in CI.
6. **Structured logging** via stdlib `logging` (portfolio-core config); no `print` in library code.
7. **Review culture:** PR template with design questions ("What alternatives were rejected? What is the rollback path?"); `engineering-playbook.md` documents the definition of done.

---

## 8. README & Presentation Layer

Root README structure (the sales document — substance only, no bio tie-ins):

1. **Hero:** title line ("Senior Data Scientist & ML/AI Engineer — architect-level portfolio"), one-paragraph positioning, link to GitHub Pages docs.
2. **Stack table** — mandated stack front and center, each mapped to where it is used.
3. **Project index** — seven projects with domain, techniques, data source (real vs. synthetic), link to docs page.
4. **Selected results** — 2–3 quantitative snippets per project, generated from actual runs.
5. **Engineering practices** — §7 summarized; link to `engineering-playbook.md` and ADRs.
6. **Contact & availability** — email, GitHub, languages, freelance availability note.
7. **No** photos, emoji clutter, or motivational filler.

Each project README: problem → design summary (linking DESIGN.md) → results with interactive plotly HTML → reproduce block → what it demonstrates for a client.

---

## 9. Execution Checklist for the Coding Agent

- [ ] **Step 1 — Scaffold:** monorepo skeleton (§4), uv workspace root, `.gitignore`, MIT LICENSE, Makefile, pre-commit, CI + docs workflows, PR template, `architecture/` with the five ADRs drafted.
- [ ] **Step 2 — Shared libs:** implement `portfolio-core` (contracts, config, plotting, synthetic data) and `portfolio-eval` (ML + RAG metrics, report builders) with tests green.
- [ ] **Step 3 — Tooling gate:** `uv sync`, `ruff check`, `ruff format --check`, `mypy`, `pytest` all green on skeleton.
- [ ] **Step 4 — Data registry:** create all six dataset cards in `data-registry/` with verified URLs, licenses, checksums, and access scripts; test each download path.
- [ ] **Step 5 — Projects in priority order:** 01 → 02 → 03 → 04 → 05 → 06 → **07 (flagship last, built on the stabilized platform)**. For each: full src layout, pydantic configs, DVC stages, tests, plotly figures, DESIGN.md, project README with real results.
- [ ] **Step 6 — DVC wiring:** root `dvc init`, per-project `dvc.yaml`, documented remote; `dvc repro` verified end-to-end on 01 and 07.
- [ ] **Step 7 — Docs & runbooks:** mkdocs-material site with ADRs, design docs, runbooks (drift, LLM cost, pipeline restore); GitHub Pages deploy verified.
- [ ] **Step 8 — Portfolio layer:** root README per §8, project index, repo topics set.
- [ ] **Step 9 — Final QA:** CI green on main; no secrets in history; every README link resolves; clean-clone reproduce test on 01 and 07; gap table vs. published Solomon optima rendered in docs.

**Definition of done:** a stranger clones, runs `make setup`, and reproduces every headline result; a client lands on the README and understands both range and engineering depth within 5 minutes; every architectural choice is traceable to a written decision record.

---

## 10. Risks & Guidance Notes

- **LLM cost/key dependency:** Project 01 degrades gracefully — provider-agnostic abstraction, mock/local mode; CI never needs a key (ADR-0004).
- **Open-data drift:** public datasets change (schema, URLs). Checksum-pinned snapshots + dataset cards turn silent breakage into loud pipeline failures.
- **Scale realism without heavyweight infra:** Project 07 slices real data (bounded months/zones) so everything runs on a laptop while still being genuinely large (GB-scale Parquet, millions of rows).
- **PyTorch honesty:** hand-written training loops in 02/04/07 — evaluators read this code; hiding behind high-level trainers reads junior.
- **DVC without cloud:** document the regenerate-locally path (`dvc repro`) so the repo is self-sufficient without a paid remote.
- **Attribution:** CC-licensed sources (Wikipedia) carry attribution in docs per the dataset card rules.
- **Scope discipline:** seven projects is the ceiling. Depth + design records per project beats an eighth demo.

---

*End of report. This document is the single source of truth for the repository build; deviations require explicit justification in a new ADR.*
