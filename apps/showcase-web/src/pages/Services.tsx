import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { FRAMEWORKS, PROVIDERS, FrameworkTile } from "../components/Frameworks";
import { usePageMeta } from "../seo";

interface Evidence {
  /** "proof: …" wording, rendered inside a mono chip. */
  label: string;
  /** SPA route — project report or live demo. */
  to: string;
}

interface Offering {
  title: string;
  outcome: string;
  elements: string[];
  deliverables: string[];
  /** Public experiments/demos that prove the offering, metric-first. */
  evidence: Evidence[];
}

const OFFERINGS: Offering[] = [
  {
    title: "AI/LLM systems",
    outcome: "Agents and assistants that answer from your documents, cite their sources, and stay inside a stated cost and latency budget.",
    elements: ["APIs (FastAPI/REST)", "Retrieval pipelines", "Structured output", "Eval harnesses"],
    deliverables: [
      "agent service with typed endpoints (FastAPI)",
      "retrieval index pipeline with pinned corpus versions",
      "faithfulness/relevance eval harness with a documented baseline",
      "per-task cost and latency budgets with fallback chains",
    ],
    evidence: [
      { label: "proof: verified-claim RAG agent", to: "/projects/01-rag-agent" },
      { label: "proof: graded agentic workflow suite", to: "/projects/09-agentic-workflows" },
    ],
  },
  {
    title: "Machine learning",
    outcome:
      "Models judged the way the business will use them: against named naive baselines, with errors priced in currency, not raw accuracy.",
    elements: ["Leakage-proof CV", "Calibrated models", "Cost curves", "Optuna HPO"],
    deliverables: [
      "leakage-proof backtests scored in time order",
      "calibrated models with uncertainty bands",
      "business-cost threshold analysis",
      "pinned CI evaluation reports",
    ],
    evidence: [
      { label: "proof: demand forecast workbench", to: "/projects/02-demand-forecasting" },
      { label: "live demo: forecast workbench", to: "/demos/forecast-workbench" },
      { label: "proof: CI-evaluated churn pipeline", to: "/projects/05-ml-pipeline-churn" },
      { label: "live demo: churn sandbox", to: "/demos/churn-sandbox" },
      { label: "proof: uplift targeting study", to: "/projects/10-uplift-experimentation" },
    ],
  },
  {
    title: "Optimization",
    outcome:
      "Routing, scheduling, and allocation solved against named benchmark instances, with the optimality gap stated per instance.",
    elements: ["Exact & heuristics", "Benchmark instances", "Runtime budgets"],
    deliverables: [
      "solver/heuristic service with typed API",
      "benchmark runner against best-known solutions",
      "gap & runtime report per instance",
    ],
    evidence: [
      { label: "proof: vehicle routing benchmark", to: "/projects/06-routing-optimization" },
    ],
  },
  {
    title: "Data engineering",
    outcome:
      "Pipelines that turn raw operational dumps into versioned, tested, analysis-ready datasets.",
    elements: ["Polars/DVC pipelines", "DQ gates", "Checksum pinning"],
    deliverables: [
      "versioned raw→feature pipelines",
      "data-quality gates in CI",
      "checksum-pinned, rebuildable datasets",
      "documented data registry entries",
    ],
    evidence: [
      { label: "proof: NYC mobility data pipeline", to: "/projects/07-open-data-mobility" },
      { label: "proof: demand forecast pipeline", to: "/projects/02-demand-forecasting" },
    ],
  },
  {
    title: "MLOps",
    outcome:
      "CI gates that block unevaluated models and failing data-quality checks before they can ship.",
    elements: ["CI eval gates", "Docker + uv", "Clean-clone runs"],
    deliverables: [
      "CI gates for evaluation & data quality",
      "dockerized, uv-managed environments",
      "pinned-baseline comparison on every run",
      "runbooks & handover docs",
    ],
    evidence: [
      { label: "proof: inference serving benchmark", to: "/projects/08-inference-serving" },
      { label: "proof: CI-evaluated churn pipeline", to: "/projects/05-ml-pipeline-churn" },
    ],
  },
  {
    title: "Interactive dashboards",
    outcome:
      "Working demos over committed payloads — every number the screen shows is checked in CI before it ships.",
    elements: ["React + Plotly", "Live endpoints", "Pinned payloads"],
    deliverables: [
      "demo frontend over the served API",
      "precomputed payload contracts",
      "parity tests pinning every shown number",
      "keyboard-navigable, axe-checked components",
    ],
    evidence: [
      { label: "live demo: forecast workbench", to: "/demos/forecast-workbench" },
      { label: "live demo: churn sandbox", to: "/demos/churn-sandbox" },
      { label: "proof: demand forecast workbench", to: "/projects/02-demand-forecasting" },
    ],
  },
  {
    title: "Full-stack product engineering",
    outcome:
      "Working product slices — typed API, web UI, deployment — that run from a clean clone.",
    elements: ["FastAPI + React", "Docker Compose", "Caddy deploy"],
    deliverables: [
      "typed API service with contract tests",
      "React frontend on shared component patterns",
      "one-command environment (uv + Docker)",
      "deployment manifests with rollback notes",
    ],
    evidence: [
      { label: "proof: served demand API", to: "/projects/07-open-data-mobility" },
      { label: "live demo: forecast workbench", to: "/demos/forecast-workbench" },
      { label: "live demo: churn sandbox", to: "/demos/churn-sandbox" },
    ],
  },
  {
    title: "APIs & model serving",
    outcome:
      "Inference endpoints designed, hosted, and measured — contracts first, with rate limits and cost budgets stated up front.",
    elements: ["FastAPI", "OpenAPI contracts", "Rate limits"],
    deliverables: [
      "versioned inference endpoints (REST)",
      "OpenAPI contract with request/response schemas",
      "rate limits and cost budgets per route",
      "latency/throughput benchmark report",
    ],
    evidence: [
      { label: "proof: inference serving benchmark", to: "/projects/08-inference-serving" },
      { label: "proof: served demand API", to: "/projects/07-open-data-mobility" },
    ],
  },
];

const PROCESS = [
  {
    step: "01",
    title: "Discovery (free, 30–45 min)",
    text: "Problem, data reality, constraints, and what \"done\" must look like. Written summary with options and rough scope.",
  },
  {
    step: "02",
    title: "Scoped pilot",
    text: "A fixed-scope, fixed-price slice (typically 1–3 weeks) that de-risks the core uncertainty — a baseline, a pipeline, an eval harness — with reproducible artifacts from day one.",
  },
  {
    step: "03",
    title: "Production build",
    text: "Iterative delivery against agreed SLOs; evaluation and DQ gates wired into CI; weekly written progress.",
  },
  {
    step: "04",
    title: "Handover",
    text: "Documentation, runbooks, and a walkthrough session. No lock-in: everything runs from a clean clone.",
  },
];

const ENGAGEMENTS = [
  {
    model: "Fixed-scope project",
    fits: "Well-defined deliverable with clear acceptance criteria",
    pricing: "fixed price — on request",
  },
  {
    model: "Retainer",
    fits: "Ongoing model/data stewardship, drift response, incremental improvements",
    pricing: "monthly — on request",
  },
  {
    model: "Advisory / audit",
    fits: "Architecture reviews, second opinions, reproducibility or MLOps audits",
    pricing: "scoped per engagement — on request",
  },
];

export function Services() {
  usePageMeta({
    title: "Services",
    description:
      "Freelance ML/AI engineering offerings — AI/LLM systems, machine learning, optimization, data engineering, MLOps, interactive dashboards, and full-stack product engineering — each backed by a public, reproducible case study with measured baselines.",
    canonical: "/services",
  });

  return (
    <>
      <section className="services-hero">
        <p className="kicker">$ services --freelance</p>
        <h1>ML/AI engineering, end to end</h1>
        <p>
          Freelance ML/AI engineering for teams that need end-to-end delivery — from
          problem framing to production systems with the engineering artifacts (decision
          records, evaluation harnesses, runbooks) that keep them operable.
        </p>
        <p>
          Every offering is backed by public, reproducible case studies — measured baselines
          and documented decisions. If it is worth saying, it is worth showing working code.
        </p>
      </section>

      <h2 className="section-title">offerings</h2>
      <div className="offerings-grid">
        {OFFERINGS.map((o) => (
          <Card key={o.title} className="offering-card">
            <h3>{o.title}</h3>
            <p className="offering-blurb">{o.outcome}</p>
            <div className="chips">
              {o.elements.map((e) => (
                <span key={e} className="chip">
                  {e}
                </span>
              ))}
            </div>
            <h4>evidence</h4>
            <div className="meta-links">
              {o.evidence.map((ev) => (
                <Link key={ev.label} className="chip-link" to={ev.to}>
                  {ev.label}
                </Link>
              ))}
            </div>
            <h4>deliverables</h4>
            <ul>
              {o.deliverables.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      <h2 className="section-title" id="frameworks">
        frameworks
      </h2>
      <p className="section-intro">
        The stack behind the work — chosen for reproducibility and longevity, not fashion.
      </p>
      <div className="frameworks-grid">
        {FRAMEWORKS.map((f) => (
          <FrameworkTile key={f.name} fw={f} />
        ))}
      </div>

      <h2 className="section-title">cloud & deployment</h2>
      <div className="cloud-plain">
        <p>
          <strong>Cloud-agnostic by design.</strong> Delivery runs on the client's platform —
          AWS, Azure, GCP, or on-premises. Pipelines are portable (Docker + uv + DVC), so
          there is no vendor lock-in and everything runs from a clean clone. Data stays
          inside the client's boundary; nothing phones home.
        </p>
        <div className="frameworks-grid providers-grid">
          {PROVIDERS.map((p) => (
            <FrameworkTile key={p.name} fw={p} />
          ))}
        </div>
      </div>

      <h2 className="section-title">process</h2>
      <ol className="process-timeline">
        {PROCESS.map((p) => (
          <li key={p.step}>
            <span className="step-num">{p.step}</span>
            <h3>{p.title}</h3>
            <p>{p.text}</p>
          </li>
        ))}
      </ol>

      <h2 className="section-title">engagement models</h2>
      <DataTable className="engagement-table">
        <thead>
          <tr>
            <th scope="col">model</th>
            <th scope="col">when it fits</th>
            <th scope="col">pricing</th>
          </tr>
        </thead>
        <tbody>
          {ENGAGEMENTS.map((e) => (
            <tr key={e.model}>
              <td>
                <strong>{e.model}</strong>
              </td>
              <td>{e.fits}</td>
              <td>{e.pricing}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="pricing-note">
        [note] pilots are deliberately small and fixed-price so the working relationship is
        tested before larger commitments.
      </p>
    </>
  );
}
