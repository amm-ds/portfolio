import type { ReactNode } from "react";
import { Card } from "../components/Card";
import { EmailIcon, GitHubIcon, LinkedInIcon, PhoneIcon } from "../components/channelIcons";
import { CONTACT_EMAIL, LINKEDIN_URL, REPO_URL } from "../config";
import { usePageMeta } from "../seo";

/** Career history as a roadmap-style vertical timeline — generic industry
 * descriptors only, no company names. Each stop: period, role, 2–3
 * achievement bullets. */
const ROLES = [
  {
    dates: "2025 — now",
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

const CONTACT_CHANNELS: { name: string; address: string; href: string; icon: ReactNode }[] = [
  {
    name: "Phone",
    address: "+34 670 881 697",
    href: "tel:+34670881697",
    icon: <PhoneIcon />,
  },
  {
    name: "Email",
    address: CONTACT_EMAIL,
    href: `mailto:${CONTACT_EMAIL}`,
    icon: <EmailIcon />,
  },
  {
    name: "GitHub",
    address: "github.com/amm-ds",
    href: REPO_URL,
    icon: <GitHubIcon />,
  },
  {
    name: "LinkedIn",
    address: "linkedin/in/alejandro-mérida-maroto",
    href: LINKEDIN_URL,
    icon: <LinkedInIcon />,
  },
];

/** How the work runs — the practices behind every case study and every
 * engagement, rendered as importance cards at the top of the page. */
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
  {
    title: "plain-language reporting",
    text: "findings are written for decision-makers, not practitioners — what was measured, what it shows, and where it stops holding.",
  },
  {
    title: "small, reversible changes",
    text: "work lands in small, reversible steps — every change stays reviewable, and any step can be reverted without archaeology.",
  },
  {
    title: "public by default",
    text: "code, metrics and case studies are public — the work is checked, not trusted, and every number can be re-run from the repository.",
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
        <div className="channel-grid channel-grid--4">
          {CONTACT_CHANNELS.map((c) => (
            <a
              key={c.name}
              className="channel-card"
              href={c.href}
              target={c.href.startsWith("http") ? "_blank" : undefined}
              rel={c.href.startsWith("http") ? "noopener noreferrer" : undefined}
            >
              <span className="channel-icon">{c.icon}</span>
              <span className="channel-text">
                <span className="channel-name">{c.name}</span>
                <span className="channel-address">{c.address}</span>
              </span>
            </a>
          ))}
        </div>
        <p className="about-facts">Barcelona · Spanish · Catalan · English</p>
      </section>

      <h2 className="section-title">how I work</h2>
      <p className="section-intro">
        Nine practices run through every engagement and every case study on this site.
      </p>
      <div className="practices-grid">
        {PRACTICES.map((p) => (
          <Card key={p.title} className="practice-card">
            <h3>{p.title}</h3>
            <p>{p.text}</p>
          </Card>
        ))}
      </div>

      <h2 className="section-title">experience</h2>
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
