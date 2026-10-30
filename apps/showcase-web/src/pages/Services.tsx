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
    elements: ["APIs (FastAPI/REST)", "Retrieval pipelines", "Structured output", "Eval harnesses"],
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
    title: "Machine learning",
    outcome:
      "Models evaluated the way the business will judge them — against named naive baselines and costed errors, not vanity scores.",
    elements: ["Leakage-proof CV", "Calibrated models", "Cost curves", "Optuna HPO"],
    deliverables: [
      "leakage-proof backtests",
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
    success:
      "Success is measured by leakage-proof backtest metrics against named naive baselines — relative MAE/WRMSSE for demand, cost-curve deltas for churn, paired-bootstrap uplift for targeting.",
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
      "Success is measured as the gap to best-known solutions on standard benchmark instances — 4.23% above published best-known across 56 Solomon cases (95% CI 3.1–5.3 pp) — under stated runtime budgets.",
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
    success:
      "Success is measured on the holdout the pipeline feeds: the committed 07 pipeline turns 41.2M raw trips into a 265-zone × hour grid whose served model cuts next-hour MAE by 28.3% versus same-hour-yesterday (MASE 0.763).",
  },
  {
    title: "MLOps",
    outcome: "A setup where bad models and broken pipelines cannot ship silently.",
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
    success:
      "Success is measured by the gates themselves: models ship only with a CI evaluation report against pinned baselines, and serving runs from a clean clone against measured SLOs (p95 0.81 s at c=1 rising to 7.80 s at c=8 on the committed bench).",
  },
  {
    title: "Interactive dashboards",
    outcome:
      "Decision tools people actually use — live demos over committed payloads, not screenshots.",
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
    success:
      "Success is measured by the pinned payload contracts: every number the dashboard shows is verified in CI — pooled test WAPE 0.491 vs 0.603 seasonal-naive, decision cost $601 vs $1,035 per 1,400 customers.",
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
    success:
      "Success is measured as working software from a clean clone: reproducible uv + Docker environments, API contract tests in CI, and deployed demos whose payloads pass parity checks on every change.",
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
