# Services

Freelance ML/AI engineering for teams that need end-to-end delivery —
from problem framing to production systems, with the engineering artifacts
(decision records, evaluation harnesses, runbooks) that keep them operable.

The work is described generically below; public case studies in this repository
demonstrate each capability end-to-end — reproducible pipelines, honest
baselines, and documented decisions. If it is worth saying, it is worth showing
working code.

## Offerings

### ML/AI systems delivery
End-to-end design and build: data contracts, training pipelines, evaluation
harnesses, deployment-ready services.
Deliverables: working system, reproducible environments (uv/Docker), evaluation
report with baselines, runbooks, handover documentation.

### Agentic AI & LLM applications
Retrieval-augmented assistants with typed tool use, structured outputs,
citation enforcement, and cost/latency SLOs — plus the evaluation harness to
prove quality and the fallback chains to keep the service up.
Deliverables: agent service (FastAPI), retrieval index pipeline, faithfulness /
relevance eval harness, cost & latency budgets.

### Data engineering
Reproducible pipelines over large, messy open or commercial data — lazy,
out-of-core processing, data-quality gates that fail loudly, checksum-pinned
snapshots, dataset registries with licenses.
Deliverables: versioned pipelines (DVC), DQ dashboards, scale and memory notes.

### Forecasting & analytics
Demand, churn, and behavioral modeling with honest backtests and
decision-ready visualizations — uncertainty bands, business-cost threshold
tuning, and decision-curve analysis.
Deliverables: leakage-proof evaluation, calibrated models, business-cost
analysis, interactive reports.

### MLOps & reproducibility audits
Versioning, CI gates, review culture, drift response — an audit of what breaks
first and the cheapest fixes, aligned with the engineering playbook published
in this repository.
Deliverables: gap report, prioritized remediation, CI/CD and DVC setup, team
playbook.

## Frameworks

The stack is deliberate and portable — each tool chosen for a written reason
(see the architecture decision records):

| Area | Framework |
|---|---|
| Typed contracts & config | [pydantic](https://docs.pydantic.dev/) · [pydantic-ai](https://ai.pydantic.dev/) |
| Classical ML | [scikit-learn](https://scikit-learn.org/) |
| Deep learning | [PyTorch](https://pytorch.org/) · [Hugging Face](https://huggingface.co/) |
| Data processing | [Polars](https://pola.rs/) |
| Visualization | [Plotly](https://plotly.com/) |
| Experiment/HPO | [Optuna](https://optuna.org/) |
| Versioning & pipelines | [DVC](https://dvc.org/) · [uv](https://docs.astral.sh/uv/) |
| Services & UI | [FastAPI](https://fastapi.tiangolo.com/) · [React](https://react.dev/) · [TypeScript](https://www.typescriptlang.org/) |
| Local LLM serving | [Ollama](https://ollama.com/) |
| LLM/RAG evaluation | [RAGAS](https://ragas.io/) · [pydantic-evals](https://ai.pydantic.dev/evals/) |

Evaluation choices are deliberate (see the architecture decision records):
**RAGAS** for retrieval-augmented systems (faithfulness, answer relevance, context
precision/recall), **pydantic-evals** for agent and workflow evaluation, with local
models (Ollama) as zero-cost judges — no evaluation budget is ever an excuse for
not evaluating.

## Cloud-agnostic delivery

Systems are built to run on **the client's platform of choice — AWS, Azure,
GCP, or on-prem**. Pipelines are portable by construction (Docker + uv + DVC),
data stays inside the client's boundary, and nothing in the deliverable depends
on a specific vendor. No lock-in: everything runs from a clean clone.

## Process

1. **Discovery (free, 30–45 min).** Problem, data reality, constraints, and
   what "done" must look like. Written summary with options and rough scope.
2. **Scoped pilot.** A fixed-scope, fixed-price slice (typically 1–3 weeks)
   that de-risks the core uncertainty — a baseline, a pipeline, an eval
   harness — with reproducible artifacts from day one.
3. **Production build.** Iterative delivery against agreed SLOs; evaluation
   and DQ gates wired into CI; weekly written progress.
4. **Handover.** Documentation, runbooks, and a walkthrough session.

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

Live, reproducible demonstrations of the above capabilities:
[project index](../projects/index.md) — each case study covers background,
objectives, data (with dataset cards), EDA, training, evaluation, results,
and conclusions, with honest naive-baseline deltas.
