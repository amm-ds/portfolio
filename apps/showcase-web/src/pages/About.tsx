import { Card } from "../components/Card";
import { PageIndex } from "../components/PageIndex";
import { ChannelCards } from "../components/ChannelCards";
import { LanguagesAvailability } from "../components/LanguagesAvailability";
import { usePageMeta } from "../seo";

/** Career history as a roadmap-style vertical timeline — generic industry
 * descriptors only, no company names. Each stop: period, role, 2–3
 * achievement bullets. */
const ROLES = [
  {
    dates: "sep 2026 — now",
    title: "Lead ML/AI engineer — alejandromerida.dev (independent)",
    points: [
      "Independent ML/AI engineering practice — this site is the showroom: two production-grade app templates and 13 reproducible experiments, every claim traced to a committed artifact.",
      "End-to-end delivery across the stack: agentic systems, page-level document AI, forecasting, optimization and model serving, deployed and measured.",
      "Engagements run discovery-first with fixed budgets, named baselines and stated limits.",
    ],
  },
  {
    dates: "2025 — aug 2026",
    title: "Lead ML/AI engineer — pharmaceutical AI (remote)",
    points: [
      "RAG chatbots and document-analysis pipelines over regulated content, cited per claim.",
      "Agentic systems with fixed tool and budget contracts; vector search at corpus scale.",
      "Stakeholder-facing lead on ML initiatives, with interview-loop support across 30+ interviews, from senior to architect.",
    ],
  },
  {
    dates: "2024 — 2025",
    title: "Senior data scientist — network telemetry (ISP data)",
    points: [
      "BigQuery ETL with data-quality controls and telemetry processing pipelines.",
      "Anomaly detection with network-wide context.",
      "Distributed ticket classification (NLP + LLM).",
    ],
  },
  {
    dates: "2023 — 2024",
    title: "Senior data scientist — manufacturing analytics",
    points: [
      "Transformer topic modeling for deviation root-cause analysis; multi-class neural classification.",
      "Bayesian hyperparameter optimization.",
      "End-to-end ML productization inside a SaaS product.",
    ],
  },
  {
    dates: "2022 — 2023",
    title: "Senior data scientist — e-commerce retail",
    points: [
      "Demand forecasting for 100k+ products with hierarchical models.",
      "Inventory optimization and dynamic-pricing experiments.",
      "MLOps: pipeline orchestration, experiment management and cloud deployments.",
    ],
  },
  {
    dates: "2021 — 2022",
    title: "Data scientist & engineer",
    points: [
      "Spark, Airflow and Redshift pipelines at scale.",
      "Dynamic-pricing proofs of concept and churn modeling across data sources.",
    ],
  },
  {
    dates: "2019 — 2021",
    title: "Data scientist — venture studio",
    points: [
      "Routing optimization and real-estate scoring across studio ventures.",
      "Customer scoring models and computer vision for content analysis.",
    ],
  },
];

/** What you receive — the practices behind every engagement, rendered as
 * importance cards at the top of the page. Client-facing: each card states a
 * deliverable or guarantee, not an internal experiment detail. */
const PRACTICES = [
  {
    title: "full repository handover",
    text: "you receive the complete repository — reproducible pipeline, pinned environment, tests and CI — so your team can rerun and extend every result without me.",
  },
  {
    title: "measured against your baseline",
    text: "nothing is trusted until it beats your naive baseline on a named metric — and the delta is stated, not implied.",
  },
  {
    title: "decisions from holdout evidence",
    text: "go/no-go calls rest on a pinned, scored-once holdout — evidence your side can verify, not impressions.",
  },
  {
    title: "performance budgets stated & met",
    text: "latency, throughput and cost budgets are agreed up front and reported against at delivery — no surprises after launch.",
  },
  {
    title: "documentation & handover walkthrough",
    text: "delivery includes documentation written for your team plus a walkthrough session — knowledge transfer is part of the work, not an extra.",
  },
  {
    title: "honest limits in every report",
    text: "every report states what the work does not establish and where the conclusions break — before you bet on them.",
  },
  {
    title: "monitoring & drift response",
    text: "after launch, monitoring watches for drift and degradation, with a response plan agreed before go-live.",
  },
  {
    title: "structured revision rounds",
    text: "feedback lands in structured revision rounds with clear scope — changes stay predictable, in time and in budget.",
  },
  {
    title: "results quality & performance first",
    text: "measured baselines, honest numbers, fast enough to be used — quality and speed are requirements, not afterthoughts.",
  },
];

export function About() {
  usePageMeta({
    title: "About",
    description:
      "Alejandro Mérida Maroto — independent ML/AI consultant in Barcelona. Experience across pharmaceutical AI, network telemetry, manufacturing analytics, e-commerce retail and venture studios; the working practices behind every case study.",
    canonical: "/about",
  });

  return (
    <>
      <section className="services-hero">
        <p className="kicker">&gt; about</p>
        <h1>Alejandro Mérida Maroto</h1>
        <p>Independent ML/AI consultant — Barcelona.</p>
        <p>
          I design, build and evaluate ML systems end to end, and I keep the code, metrics
          and case studies public and auditable.
        </p>
        <p>
          <a
            href="https://amm-ds.github.io/portfolio/site/how-this-was-built/"
            target="_blank"
            rel="noopener noreferrer"
          >
            How this portfolio was built — AI use disclosed →
          </a>
        </p>
        <PageIndex
          items={[
            { id: "how-i-work", label: "how I work" },
            { id: "experience", label: "experience" },
          ]}
        />
        <ChannelCards />
        <LanguagesAvailability />
      </section>

      <h2 className="section-title" id="how-i-work">how I work</h2>
      <p className="section-intro">
        Nine practices shape every engagement — each one is something you receive, stated up
        front.
      </p>
      <div className="practices-grid">
        {PRACTICES.map((p) => (
          <Card key={p.title} className="practice-card">
            <h3>{p.title}</h3>
            <p>{p.text}</p>
          </Card>
        ))}
      </div>

      <h2 className="section-title" id="experience">experience</h2>
      <ol className="timeline">
        {ROLES.map((r) => (
          <li key={r.dates} className="timeline-item">
            <p className="timeline-period">{r.dates}</p>
            <h3>{r.title}</h3>
            <ul>
              {r.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </>
  );
}
