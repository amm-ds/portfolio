import { Link } from "react-router-dom";
import { FRAMEWORKS, FrameworkTile } from "../components/Frameworks";

const OFFERINGS = [
  {
    title: "ML/AI systems delivery",
    blurb:
      "End-to-end design and build of production ML systems — from data contracts and training pipelines to evaluation harnesses and deployment-ready services.",
    deliverables: [
      "working system",
      "DVC/CI reproducibility",
      "evaluation report with baselines",
      "runbooks",
      "handover documentation",
    ],
  },
  {
    title: "Agentic AI & LLM applications",
    blurb:
      "Retrieval-augmented assistants and agents with typed tool use, structured outputs and citation enforcement — delivered with the evaluation harness to prove quality and the budgets to run it.",
    deliverables: [
      "agent service (FastAPI)",
      "retrieval index pipeline",
      "faithfulness/relevance eval harness",
      "cost & latency budgets",
      "fallback chains",
    ],
  },
  {
    title: "Data engineering",
    blurb:
      "Reproducible pipelines over large, messy open or commercial data — lazy, out-of-core processing, data-quality gates that fail loudly, checksum-pinned snapshots.",
    deliverables: [
      "versioned pipeline (DVC)",
      "dataset registry with licenses and checksums",
      "DQ dashboards",
      "scale notes",
    ],
  },
  {
    title: "Forecasting & analytics",
    blurb:
      "Demand, churn and behavioral modeling with honest backtests and decision-ready visualizations — including uncertainty bands and business-cost threshold tuning.",
    deliverables: [
      "leakage-proof evaluation",
      "calibrated models",
      "business-cost analysis",
      "interactive reports",
    ],
  },
  {
    title: "MLOps & reproducibility audits",
    blurb:
      "Versioning, CI gates, review culture, drift response — an audit of what breaks first and the cheapest fixes, aligned with a published engineering playbook.",
    deliverables: [
      "gap report",
      "prioritized remediation",
      "CI/CD and DVC setup",
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
        <h1>Senior ML/AI engineering, end to end</h1>
        <p>
          Freelance ML/AI engineering for teams that need senior, end-to-end delivery — from
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
          <div key={o.title} className="offering-card">
            <h3>{o.title}</h3>
            <p className="offering-blurb">{o.blurb}</p>
            <h4>deliverables</h4>
            <ul>
              {o.deliverables.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </div>
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
      <div className="cloud-block">
        <p>
          <strong>Cloud-agnostic by design.</strong> Delivery runs on the client's platform —
          AWS, Azure, GCP, or on-premises. Pipelines are portable (Docker + uv + DVC), so
          there is no vendor lock-in and everything runs from a clean clone. Data stays
          inside the client's boundary; nothing phones home.
        </p>
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
      <div className="engagement-table">
        <table>
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
        </table>
      </div>
      <p className="pricing-note">
        [note] pilots are deliberately small and fixed-price so the working relationship is
        tested before larger commitments.
      </p>

      <h2 className="section-title">proof</h2>
      <div className="state-box">
        Every offering above is backed by a public, reproducible case study — real pipelines,
        real metrics, interactive figures.{" "}
        <Link to="/projects">browse the case studies →</Link>
      </div>

      <h2 className="section-title">contact & availability</h2>
      <div className="contact-block">
        <ul>
          <li>
            GitHub:{" "}
            <a href="https://github.com/amm-ds" target="_blank" rel="noreferrer">
              amm-ds
            </a>
          </li>
          <li>Availability: open to freelance and consulting engagements; typical response within 48 hours.</li>
          <li>Languages: English, Spanish.</li>
          <li>Location/timezone: flexible overlap with EU and US hours.</li>
        </ul>
      </div>
    </>
  );
}
