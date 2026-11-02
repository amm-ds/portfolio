import { Card } from "../components/Card";
import { CONTACT_EMAIL, REPO_URL } from "../config";
import { usePageMeta } from "../seo";

/** Career history, generic industry descriptors only — no company names. */
const ROLES = [
  {
    dates: "2025 — now",
    title: "Lead ML/AI engineer — pharmaceutical AI (remote)",
    text: "RAG chatbots and document-analysis pipelines over regulated content, agentic systems with fixed tool and budget contracts, and vector search at corpus scale. Stakeholder-facing lead on ML initiatives, with interview-loop support across 30+ interviews, from senior to architect.",
  },
  {
    dates: "2024 — 2025",
    title: "Senior data scientist — network telemetry (ISP data)",
    text: "BigQuery ETL with data-quality controls, anomaly detection with network-wide context, distributed ticket classification (NLP + LLM), and telemetry processing pipelines.",
  },
  {
    dates: "2023 — 2024",
    title: "Senior data scientist — manufacturing analytics",
    text: "Transformer topic modeling for deviation root-cause analysis, multi-class neural classification, Bayesian hyperparameter optimization, and end-to-end ML productization inside a SaaS product.",
  },
  {
    dates: "2022 — 2023",
    title: "Senior data scientist — e-commerce retail",
    text: "Demand forecasting for 100k+ products with hierarchical models, inventory optimization, dynamic-pricing experiments, and MLOps (Airflow, MLflow, AWS).",
  },
  {
    dates: "2021 — 2022",
    title: "Data scientist & engineer",
    text: "Spark, Airflow and Redshift pipelines at scale, dynamic-pricing proofs of concept, and churn modeling across data sources.",
  },
  {
    dates: "2019 — 2021",
    title: "Data scientist — venture studio",
    text: "Routing optimization, real-estate and customer scoring, and computer vision for content analysis across studio ventures.",
  },
];

const EDUCATION = [
  "Master in Big Data & Business Intelligence (UOC)",
  "Business & IT (UAB)",
  "Postgraduate in financial markets (UA)",
  "MITx — Machine Learning with Python",
  "GCP Big Data & ML fundamentals",
];

/** How the work runs, in narrative form — the practices behind every case
 * study and every engagement. */
const PRACTICES = [
  {
    title: "reproducible pipelines",
    text: "every result rebuilds from a clean state — no notebook ghosts, no \"works on my machine\".",
  },
  {
    title: "pinned data with checksums",
    text: "dataset cards pin source, license, checksum and snapshot date before any modeling starts.",
  },
  {
    title: "scored-once evaluation",
    text: "models are scored in CI against a pinned holdout — a metric that changed is flagged, not shipped.",
  },
  {
    title: "honest baselines",
    text: "every model is judged against a named naive baseline, and the delta is stated, not implied.",
  },
  {
    title: "tested code",
    text: "unit and property tests on the validators, coverage gates in CI — a fix without a regression test is not a fix.",
  },
  {
    title: "stated limits",
    text: "every report says what the work does not establish, including where the conclusions break.",
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
        <ul className="about-contact">
          <li>Barcelona</li>
          <li>
            <a href="tel:+34670881697">+34 670 881 697</a>
          </li>
          <li>
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
          </li>
          <li>
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              github.com/amm-ds
            </a>
          </li>
          <li>Spanish · Catalan · English</li>
        </ul>
      </section>

      <h2 className="section-title">experience</h2>
      <div className="roles-grid">
        {ROLES.map((r) => (
          <Card key={r.dates} className="role-card">
            <p className="role-dates">{r.dates}</p>
            <h3>{r.title}</h3>
            <p>{r.text}</p>
          </Card>
        ))}
      </div>

      <h2 className="section-title">education &amp; certifications</h2>
      <Card className="education-card">
        <ul>
          {EDUCATION.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </Card>

      <h2 className="section-title">how I work</h2>
      <p className="section-intro">
        Six practices run through every engagement and every case study on this site.
      </p>
      <Card className="practices-strip">
        <ul>
          {PRACTICES.map((p) => (
            <li key={p.title}>
              <strong>{p.title}</strong> — {p.text}
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
