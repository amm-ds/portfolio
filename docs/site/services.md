# Services

Freelance ML/AI engineering for teams that need senior, end-to-end delivery —
from problem framing to production systems with the engineering artifacts
(decision records, evaluation harnesses, runbooks) that keep them operable.

Every engagement is backed by the public case studies in this repository —
reproducible pipelines, honest baselines, and documented decisions. If it is
worth saying, it is worth showing working code.

## Offerings

### ML/AI systems delivery
End-to-end design and build: data contracts, training pipelines, evaluation
harnesses, deployment-ready services.
Deliverables: working system, DVC/CI reproducibility, evaluation report with
baselines, runbooks, handover documentation.

### Agentic AI & RAG applications
Retrieval-augmented assistants with typed tool use, structured outputs,
citation enforcement, and cost/latency SLOs — plus the evaluation harness to
prove quality (Project 01 is the reference build).
Deliverables: agent service (FastAPI), retrieval index pipeline, faithfulness/
relevance eval harness, cost & latency budgets, fallback chains.

### Data engineering
Reproducible pipelines over large, messy open or commercial data — lazy,
out-of-core processing, data-quality gates that fail loudly, checksum-pinned
snapshots (Project 07 processed 41M real trips on a laptop budget).
Deliverables: versioned pipeline (DVC), dataset registry with licenses and
checksums, DQ dashboards, scale notes.

### Forecasting & analytics
Demand, churn, and behavioral modeling with honest backtests and
decision-ready visualizations — including uncertainty bands and business-cost
threshold tuning (Projects 02, 05, 07).
Deliverables: leakage-proof evaluation, calibrated models, business-cost
analysis, interactive reports.

### MLOps & reproducibility audits
Versioning, CI gates, review culture, drift response — an audit of what
breaks first and the cheapest fixes, aligned with the engineering playbook
published in this repository.
Deliverables: gap report, prioritized remediation, CI/CD and DVC setup,
team playbook.

## Process

1. **Discovery (free, 30–45 min).** Problem, data reality, constraints, and
   what "done" must look like. Written summary with options and rough scope.
2. **Scoped pilot.** A fixed-scope, fixed-price slice (typically 1–3 weeks)
   that de-risks the core uncertainty — a baseline, a pipeline, an eval
   harness — with reproducible artifacts from day one.
3. **Production build.** Iterative delivery against agreed SLOs; evaluation
   and DQ gates wired into CI; weekly written progress.
4. **Handover.** Documentation, runbooks, and a walkthrough session. No
   lock-in: everything runs from a clean clone.

## Engagement models

| Model | When it fits |
|---|---|
| **Fixed-scope project** | Well-defined deliverable with clear acceptance criteria |
| **Retainer** | Ongoing model/data stewardship, drift response, incremental improvements |
| **Advisory / audit** | Architecture reviews, second opinions, reproducibility or MLOps audits |

Pricing is scoped per engagement — on request. Pilots are deliberately
small and fixed-price so the working relationship is tested before larger
commitments.

## Contact & availability

- GitHub: [amm-ds](https://github.com/amm-ds)
- Availability: open to freelance and consulting engagements; typical
  response within 48 hours.
- Languages: English, Spanish.
- Location/timezone: flexible overlap with EU and US hours.

## Case studies

| Project | What it demonstrates |
|---|---|
| [01 — RAG & Agentic AI Assistant](../projects/01-rag-agent.md) | Typed agentic AI with evaluation harness and cost SLOs |
| [07 — Urban Mobility Demand Intelligence](../projects/07-open-data-mobility.md) | GB-scale open data, forecasting, weather insight |
| [06 — Routing Optimization](../projects/06-routing-optimization.md) | Optimization against published benchmarks |
| [04 — NLP Classification](../projects/04-nlp-classification.md) | Deep learning with hand-written training loops |
| [05 — Churn Modeling](../projects/05-ml-pipeline-churn.md) | Deployment-grade sklearn pipelines, business-cost decisions |
| [03 — Anomaly Detection](../projects/03-anomaly-detection.md) | Unsupervised detection with honest failure analysis |
| [02 — Demand Forecasting](../projects/02-demand-forecasting.md) | Leakage-proof time-series evaluation |
