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
  /** One sentence: how success is evaluated (no revenue promises). */
  success: string;
}

const OFFERINGS: Offering[] = [
  {
    title: "AI/LLM systems",
    outcome: "Assistants and agents that cite their sources and stay inside their budgets.",
    elements: ["APIs (FastAPI/REST)", "Inference & serving", "Eval/HPO (Optuna)"],
    deliverables: [
      "agent service (FastAPI)",
      "retrieval index pipeline",
      "faithfulness/relevance eval harness",
      "cost & latency budgets with fallback chains",
    ],
    evidence: [
      { label: "proof: verified-claim RAG agent", to: "/projects/01-rag-agent" },
      { label: "proof: graded agentic workflow suite", to: "/projects/09-agentic-workflows" },
    ],
    success:
      "Success is measured on the eval harness — faithfulness and answer relevance against a documented baseline, plus per-task cost and latency budgets — never on demo impressions.",
  },
  {
    title: "Predictive analytics",
    outcome:
      "Models evaluated the way the business will judge them — with costs, not vanity scores.",
    elements: ["Data pipelines", "Viz (Plotly/React)", "Leakage-proof CV"],
    deliverables: [
      "leakage-proof backtests",
      "calibrated models with uncertainty bands",
      "business-cost threshold analysis",
      "interactive reports & dashboards",
    ],
    evidence: [
      { label: "proof: demand forecast workbench", to: "/projects/02-demand-forecasting" },
      { label: "live demo: forecast workbench", to: "/demos/forecast-workbench" },
      { label: "proof: CI-evaluated churn pipeline", to: "/projects/05-ml-pipeline-churn" },
      { label: "live demo: churn sandbox", to: "/demos/churn-sandbox" },
      { label: "proof: uplift targeting study", to: "/projects/10-uplift-experimentation" },
    ],
    success:
      "Success is measured by leakage-proof backtest metrics against named naive baselines — relative MAE/WRMSSE for demand, cost-curve deltas for churn, paired-bootstrap uplift for targeting.",
  },
  {
    title: "ML engineering & MLOps",
    outcome: "A setup where bad models and broken pipelines cannot ship silently.",
    elements: [
      "Data pipelines (Polars/DVC)",
      "MLOps/CI (Actions/Docker)",
      "uv",
      "Eval/HPO (Optuna)",
    ],
    deliverables: [
      "CI gates for evaluation & data quality",
      "dockerized, uv-managed environments",
      "prioritized remediation gap report",
      "team playbook, runbooks & handover docs",
    ],
    evidence: [
      { label: "proof: inference serving benchmark", to: "/projects/08-inference-serving" },
      { label: "proof: CI-evaluated churn pipeline", to: "/projects/05-ml-pipeline-churn" },
    ],
    success:
      "Success is measured by the gates themselves: models ship only with a CI evaluation report against pinned baselines, and the system runs from a clean clone with measured latency/throughput SLOs.",
  },
  {
    title: "Optimization",
    outcome:
      "Routing, scheduling, and allocation solved against benchmark instances — with the optimality gap stated, not hidden.",
    elements: ["Exact & heuristics", "Benchmark instances", "Runtime budgets"],
    deliverables: [
      "solver/heuristic service with typed API",
      "benchmark runner against best-known solutions",
      "gap & runtime report per instance",
    ],
    evidence: [
      { label: "proof: vehicle routing benchmark", to: "/projects/06-routing-optimization" },
    ],
    success:
      "Success is measured as the gap to best-known solutions on standard benchmark instances (within 4.23% across 56 CVRPLIB cases) under stated runtime budgets.",
  },
  {
    title: "Anomaly detection",
    outcome:
      "Incident and fraud detection with an explicit alert budget — the recall vs false-positive trade-off quantified, not hand-waved.",
    elements: ["Unsupervised detection", "Streaming telemetry", "Alert budgets"],
    deliverables: [
      "detection service over telemetry streams",
      "recall-vs-alert-budget evaluation",
      "alerting integration with drift runbook",
    ],
    evidence: [
      { label: "proof: incident detection w/ alert budget", to: "/projects/03-anomaly-detection" },
    ],
    success:
      "Success is measured as recall at a fixed alert budget versus naive detectors, with the false-positive cost curve published rather than implied.",
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
      "Freelance ML/AI engineering offerings — AI/LLM systems, predictive analytics, MLOps, optimization, anomaly detection — each backed by a public, reproducible case study with measured baselines.",
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
            <p className="offering-blurb">
              <strong>how success is measured ::</strong> {o.success}
            </p>
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
