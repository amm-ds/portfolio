# Services

Freelance ML/AI engineering for teams that need end-to-end delivery — from
problem framing to production systems with the engineering artifacts
(decision records, evaluation harnesses, runbooks) that keep them operable.

## Offerings

Seven generic offerings, each backed by public, reproducible case studies —
measured against named naive baselines, with no revenue promises:

1. **AI/LLM systems** — assistants and agents that cite their sources and
   stay inside their budgets: FastAPI services, retrieval pipelines,
   structured output, eval harnesses, cost/latency budgets with fallback
   chains. *Evidence: the verified-claim RAG agent (01) and the graded agentic
   workflow suite (09).*
2. **Machine learning** — models evaluated the way the business will judge
   them: leakage-proof backtests, calibrated uncertainty bands, business-cost
   threshold analysis, Optuna HPO, pinned CI evaluation reports. *Evidence:
   the demand forecast workbench (02), the CI-evaluated churn pipeline (05),
   the uplift targeting study (10).*
3. **Optimization** — routing, scheduling, and allocation solved against
   benchmark instances, with the optimality gap stated, not hidden: typed
   solver APIs, benchmark runners, gap-and-runtime reports per instance.
   *Evidence: the vehicle routing benchmark — 4.23% above published
   best-known across 56 Solomon cases (06).*
4. **Data engineering** — pipelines that turn raw operational dumps into
   versioned, tested, analysis-ready datasets: Polars/DVC pipelines, DQ gates
   in CI, checksum-pinned rebuildable datasets, documented registry entries.
   *Evidence: the NYC mobility pipeline over 41.2M trips (07) and the demand
   forecast pipeline (02).*
5. **MLOps** — a setup where bad models and broken pipelines cannot ship
   silently: CI evaluation gates, Docker + uv environments, clean-clone
   reruns, runbooks and handover docs. *Evidence: the inference serving
   benchmark (08) and the churn pipeline's CI-evaluated registry (05).*
6. **Interactive dashboards** — decision tools over live endpoints and
   committed payloads, not screenshots: demo frontends, precomputed payload
   contracts, parity tests pinning every shown number, keyboard-navigable
   axe-checked components. *Evidence: the forecast workbench and churn
   sandbox demos in this repo's showcase app.*
7. **Full-stack product engineering** — working product slices that run from a
   clean clone: typed API services with contract tests, React frontends,
   one-command uv + Docker environments, deployment manifests. *Evidence: the
   served demand API (07) and the showcase app itself.*

Success is stated per offering on the Services page — on the eval harness,
the backtest metrics, the benchmark gap, or the pinned payload contracts —
never on demo impressions.

## Where the full page lives

The canonical services page — per-offering deliverables, process, engagement
models, and the framework logo grid — is a component of the showcase app:

- **Source:** [apps/showcase-web/src/pages/Services.tsx](https://github.com/amm-ds/portfolio/blob/main/apps/showcase-web/src/pages/Services.tsx)
  (also the framework/provider logo tiles: [Frameworks.tsx](https://github.com/amm-ds/portfolio/blob/main/apps/showcase-web/src/components/Frameworks.tsx))
- **Interactive rendering:** run the app locally — `make docker-up` →
  http://localhost:8000/services. A public deployment is not live yet; the
  exact single-container build/run flow and its status are tracked in
  [deploy/DEPLOY.md](https://github.com/amm-ds/portfolio/blob/main/deploy/DEPLOY.md).

The frameworks behind the work (shown with logos on that page): pydantic,
pydantic-ai, Ollama, scikit-learn, PyTorch, Polars, Plotly, DVC, uv, FastAPI,
React, TypeScript, Optuna, RAGAS, pydantic-evals, Hugging Face. Delivery is
cloud-agnostic — AWS, Azure, Google Cloud, or on-premises; Docker + uv + DVC
pipelines port anywhere, and data stays inside the client's boundary.

## Process & engagement models

Discovery (free, 30–45 min) → scoped fixed-price pilot → production build
against agreed SLOs → handover with runbooks and a walkthrough. Engagement
models: fixed-scope project, monthly retainer, or scoped advisory/audit.

Case studies behind the offerings: [project index](../projects/index.md).
To start an engagement, see [Contact](contact.md).
