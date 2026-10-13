import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMetrics } from "../api";
import { FrameworkTile, FRAMEWORKS } from "../components/Frameworks";
import { Terminal } from "../components/Terminal";
import { useTypedScript } from "../hooks/useTyped";

const HERO_SCRIPT = [
  { cmd: "whoami", output: "data scientist & ml/ai engineer" },
  { cmd: "dvc repro", output: "7 projects · 41.2M trips · 230+ tests · all green" },
];

const CAPABILITIES = [
  {
    title: "ML/AI systems",
    bullets: [
      "End-to-end design and delivery: data contracts, training, evaluation, deployment",
      "Honest baselines and leakage-proof evaluation harnesses",
      "Reproducible pipelines (DVC/CI) with runbooks and handover docs",
    ],
  },
  {
    title: "Agentic AI & LLM applications",
    bullets: [
      "RAG assistants with typed tool use and structured outputs",
      "Citation enforcement, faithfulness/relevance eval harnesses",
      "Cost and latency budgets with fallback chains",
    ],
  },
  {
    title: "Data engineering & forecasting",
    bullets: [
      "Versioned pipelines over large, messy open or commercial data",
      "Demand, churn and behavioral models with calibrated uncertainty",
      "Decision-ready reports: business-cost thresholds, not just metrics",
    ],
  },
];

const FEATURED = [
  { id: "01-rag-agent", label: "01", domain: "Agentic AI / RAG" },
  { id: "07-open-data-mobility", label: "07", domain: "Forecasting / open data" },
  { id: "03-anomaly-detection", label: "03", domain: "Unsupervised detection" },
];

const STRIP_FRAMEWORKS = ["pydantic", "FastAPI", "Polars", "DVC", "React", "TypeScript", "PyTorch", "scikit-learn"];

function HeroTerminal() {
  const { lines, currentCmd, done } = useTypedScript(HERO_SCRIPT);
  return (
    <Terminal title="alejandro@amm-ds: ~">
      {lines.map((line, i) => (
        <div key={i}>
          <p className="cmd">{line.cmd}</p>
          {line.output && <p className="out">{line.output}</p>}
        </div>
      ))}
      {!done && (
        <p className="cmd-partial">
          {currentCmd}
          <span className="cursor" aria-hidden="true" />
        </p>
      )}
      {done && (
        <p className="cmd-partial">
          <span className="cursor" aria-hidden="true" />
        </p>
      )}
    </Terminal>
  );
}

/** One key number for a featured case study, from its live metrics (hidden if none yet). */
function KeyNumber({ pid }: { pid: string }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    getMetrics(pid)
      .then((m) => {
        if (cancelled || !m) return;
        const run = Object.keys(m)[0];
        const entries = run ? Object.entries(m[run]) : [];
        const numeric = entries.find((e): e is [string, number] => typeof e[1] === "number");
        if (run && numeric) {
          const value = Number.isInteger(numeric[1]) ? String(numeric[1]) : numeric[1].toFixed(4);
          setText(`${numeric[0]}: ${value}`);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [pid]);
  if (!text) return null;
  return <span className="key-number">{text}</span>;
}

export function Home() {
  const strip = FRAMEWORKS.filter((f) => STRIP_FRAMEWORKS.includes(f.name));
  return (
    <>
      <section className="hero">
        <h1>Data Scientist &amp; ML Engineer</h1>
        <p className="hero-sub">
          End-to-end ML/AI systems, reproducible pipelines and honest evaluation — delivered
          as working systems with the engineering artifacts to keep them operable.
          Location-independent; available for freelance and contract engagements.
        </p>
        <HeroTerminal />
      </section>

      <h2 className="section-title">what i do</h2>
      <div className="offerings-grid">
        {CAPABILITIES.map((c) => (
          <div key={c.title} className="offering-card">
            <h3>{c.title}</h3>
            <ul>
              {c.bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
            <p className="card-link">
              <Link to="/services">services →</Link>
            </p>
          </div>
        ))}
      </div>

      <h2 className="section-title">selected case studies</h2>
      <div className="project-grid">
        {FEATURED.map((f) => (
          <Link key={f.id} to={`/projects/${f.id}`} className="project-card case-card">
            <div className="project-card-top">
              <div>
                <h3>
                  <span className="rail-num">{f.label} · </span>
                  {f.domain}
                </h3>
                <p className="domain">{f.id}</p>
              </div>
            </div>
            <p className="data">
              <KeyNumber pid={f.id} />
            </p>
          </Link>
        ))}
      </div>
      <p className="card-link">
        <Link to="/projects">all 7 projects →</Link>
      </p>

      <h2 className="section-title">frameworks</h2>
      <div className="framework-strip">
        {strip.map((f) => (
          <FrameworkTile key={f.name} fw={f} />
        ))}
        <Link to="/services#frameworks" className="framework-more">
          all →
        </Link>
      </div>

      <div className="cta-band">
        <p>
          <strong>Available now.</strong> Freelance and contract engagements, EU/US timezone
          overlap, typical response within 48 hours.
        </p>
        <p className="cta-links">
          <Link to="/services">/services</Link> ·{" "}
          <a href="https://github.com/amm-ds/portfolio" target="_blank" rel="noreferrer">
            github
          </a>
        </p>
      </div>
    </>
  );
}
