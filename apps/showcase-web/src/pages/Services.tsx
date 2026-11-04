import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { FRAMEWORKS, PROVIDERS, FrameworkTile } from "../components/Frameworks";
import { usePageMeta } from "../seo";

interface Offering {
  title: string;
  outcome: string;
  elements: string[];
  deliverables: string[];
}

/** Offering tags are plain capability wording — blue chips, no framework or
 * library names (the frameworks section carries the stack, which adapts to
 * the task at hand). */
const OFFERINGS: Offering[] = [
  {
    title: "Agentic AI & LLM systems",
    outcome:
      "Agents and assistants designed to answer from your documents, cite every claim, and stay inside fixed tool, cost and latency budgets.",
    elements: ["Retrieval pipelines", "Structured output", "Eval harnesses", "Cost budgets"],
    deliverables: [
      "retrieval pipeline over your documents with pinned corpus versions",
      "agents with fixed tool, cost and latency budgets",
      "eval harness scoring faithfulness, relevance and cost per release",
      "runbook for adding documents, re-indexing and re-running evals",
    ],
  },
  {
    title: "Machine learning & deep learning",
    outcome:
      "Models designed, trained and evaluated end to end against named naive baselines, with errors priced in business terms rather than raw accuracy.",
    elements: ["Leakage-proof CV", "Calibrated models", "Cost curves", "Hyperparameter search"],
    deliverables: [
      "training pipeline with leakage-proof cross-validation",
      "calibrated model shipped with named naive baselines",
      "error-cost analysis translating metrics into business terms",
      "evaluation report stating where the model fails",
    ],
  },
  {
    title: "Optimization",
    outcome:
      "Routing, scheduling and allocation problems solved against named benchmark instances, with the optimality gap and runtime stated per instance.",
    elements: ["Exact & heuristics", "Benchmark instances", "Runtime budgets", "Gap reports"],
    deliverables: [
      "solver tuned against named benchmark instances",
      "runtime and optimality-gap report per instance",
      "deployment that stays inside agreed runtime budgets",
      "reproducible benchmark suite for future comparisons",
    ],
  },
  {
    title: "Data engineering",
    outcome:
      "Pipelines that turn raw operational dumps into versioned, tested, analysis-ready datasets with quality gates in CI — built to be handed over, not babysat.",
    elements: ["Pipeline orchestration", "DQ gates", "Checksum pinning", "Data registry"],
    deliverables: [
      "versioned, checksummed datasets in a documented registry",
      "data-quality gates running in CI on every change",
      "orchestrated pipeline rerunnable from the README",
      "handover walkthrough with a data dictionary",
    ],
  },
  {
    title: "MLOps",
    outcome:
      "CI gates that block unevaluated models and failing data-quality checks before they can ship — operable by the client's own team from day one.",
    elements: ["CI eval gates", "Reproducible environments", "Clean-clone runs", "Drift checks"],
    deliverables: [
      "CI eval gates that block unevaluated model changes",
      "environments that rebuild from a clean clone",
      "drift checks with alerts wired into your channels",
      "runbooks your own team can operate",
    ],
  },
  {
    title: "Interactive dashboards",
    outcome:
      "Working demos over committed payloads — every number the screen shows is checked in CI before it ships, and the whole slice runs from a clean clone.",
    elements: ["Interactive charting", "Live endpoints", "Pinned payloads", "Parity tests"],
    deliverables: [
      "deployed dashboard reading only committed, versioned payloads",
      "CI parity tests checking every number on screen",
      "one-command run from a clean clone",
      "documented, accessibility-checked chart set",
    ],
  },
  {
    title: "Full-stack engineering",
    outcome:
      "Typed API, web UI and deployment wired together as one product slice that runs from a clean clone — full-stack delivery, not a throwaway prototype.",
    elements: ["API/UI integration", "Composable deployments", "Reverse-proxy deploys", "Contract tests"],
    deliverables: [
      "typed API and web UI wired into one deployable slice",
      "contract tests between frontend and API",
      "composable deployment runnable from a clean clone",
      "documentation covering setup, operation and extension",
    ],
  },
  {
    title: "APIs & model serving",
    outcome:
      "Versioned inference endpoints with explicit contracts, rate limits and measured latency/throughput on target hardware — sized, not guessed.",
    elements: ["OpenAPI contracts", "Rate limits", "Latency budgets", "Throughput reports"],
    deliverables: [
      "versioned endpoint with an explicit contract",
      "rate limits and authentication set to your requirements",
      "latency and throughput measured on your target hardware",
      "capacity report per dollar at agreed load",
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
  {
    step: "05",
    title: "Revisions",
    text: "Structured revision rounds after delivery: feedback is addressed, the evaluation re-run, and the report updated until the numbers hold up.",
  },
];

const ENGAGEMENTS = [
  {
    model: "Fixed-scope project",
    fits: "Well-defined deliverable with clear acceptance criteria — includes structured revision rounds",
    pricing: "fixed price — on request",
  },
  {
    model: "Retainer",
    fits: "Ongoing model/data stewardship, drift response, incremental improvements — revisions roll month to month",
    pricing: "monthly — on request",
  },
  {
    model: "Advisory / audit",
    fits: "System design reviews, second opinions, reproducibility or MLOps audits",
    pricing: "scoped per engagement — on request",
  },
];

export function Services() {
  usePageMeta({
    title: "Services",
    description:
      "Freelance ML/AI engineering offerings — agentic AI & LLM systems, machine learning, optimization, data engineering, MLOps, interactive dashboards, full-stack engineering, and APIs & model serving — each backed by a public, reproducible case study with measured baselines.",
    canonical: "/services",
  });

  return (
    <>
      <section className="services-hero">
        <p className="kicker">&gt; services</p>
        <h1>ML/AI engineering, end to end</h1>
        <p>
          Independent ML/AI engineering for teams and enterprises that need end-to-end
          delivery — from problem framing to production systems, with the decision records,
          evaluation harnesses and runbooks that keep them operable after handover.
        </p>
        <p>
          Every offering below is backed by a public case study on this site — the same
          pipelines, metrics and stated limits you would receive.
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
          <li key={p.title}>
            {p.step && <span className="step-num">{p.step}</span>}
            <h3>{p.title}</h3>
            <p>{p.text}</p>
          </li>
        ))}
      </ol>

      <h2 className="section-title">engagement models</h2>
      <p className="section-intro">
        Every engagement includes structured revision rounds after delivery — feedback,
        re-evaluation and updated reports are part of the scope, not an extra.
      </p>
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
