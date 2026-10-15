import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { FRAMEWORKS, PROVIDERS, FrameworkTile } from "../components/Frameworks";

interface Offering {
  title: string;
  outcome: string;
  elements: string[];
  deliverables: string[];
}

const OFFERINGS: Offering[] = [
  {
    title: "ML/AI systems delivery",
    outcome: "Production ML systems designed, built, and handed over — not notebooks.",
    elements: ["Full-stack (TS/React)", "APIs (FastAPI/REST)", "Inference & serving"],
    deliverables: [
      "working system, runnable from a clean clone",
      "DVC/CI reproducibility",
      "evaluation report with baselines",
      "runbooks & handover documentation",
    ],
  },
  {
    title: "Agentic AI & LLM applications",
    outcome: "Assistants and agents that cite their sources and stay inside their budgets.",
    elements: ["APIs (FastAPI/REST)", "Inference & serving", "Eval/HPO (Optuna)"],
    deliverables: [
      "agent service (FastAPI)",
      "retrieval index pipeline",
      "faithfulness/relevance eval harness",
      "cost & latency budgets with fallback chains",
    ],
  },
  {
    title: "Data engineering",
    outcome: "Pipelines over large, messy data that fail loudly and re-run cheaply.",
    elements: ["Data pipelines (Polars/DVC)", "Out-of-core processing"],
    deliverables: [
      "versioned pipeline (DVC)",
      "dataset registry with licenses & checksums",
      "data-quality gates",
      "scale notes",
    ],
  },
  {
    title: "Forecasting & analytics",
    outcome: "Models evaluated the way the business will judge them — with costs, not vanity scores.",
    elements: ["Data pipelines", "Viz (Plotly/React)"],
    deliverables: [
      "leakage-proof backtests",
      "calibrated models with uncertainty bands",
      "business-cost threshold analysis",
      "interactive reports",
    ],
  },
  {
    title: "Interactive dashboards & visualization",
    outcome: "Decision-ready frontends on top of models and pipelines.",
    elements: ["Viz (Plotly/React)", "Full-stack (TS/React)"],
    deliverables: [
      "plotly figures & dashboards",
      "react frontends over the model APIs",
      "self-updating reports from pipeline artifacts",
    ],
  },
  {
    title: "MLOps, evaluation & CI",
    outcome: "A setup where bad models and broken pipelines cannot ship silently.",
    elements: ["Eval/HPO (Optuna)", "Leakage-proof CV", "MLOps/CI (Actions/Docker)", "uv"],
    deliverables: [
      "CI gates for evaluation & data quality",
      "dockerized, uv-managed environments",
      "prioritized remediation gap report",
      "team playbook",
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
          Every engagement is backed by public, reproducible case studies — honest baselines
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
