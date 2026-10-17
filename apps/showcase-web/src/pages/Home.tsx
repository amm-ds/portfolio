import { Link } from "react-router-dom";
import { Terminal } from "../components/Terminal";
import { useTypedScript } from "../hooks/useTyped";

export const HERO_SCRIPT = [
  { cmd: "whoami", output: "data scientist & ml engineer" },
  { cmd: "focus", output: "agentic ai · forecasting · machine learning · optimization · data engineering" },
  { cmd: "stack", output: "pydantic-ai · pytorch · polars · scikit-learn · plotly · dvc" },
  { cmd: "principles", output: "reproducible pipelines · honest baselines · production-grade code" },
];

const GO_LINKS = [
  {
    to: "/projects",
    label: "projects",
    line: "10 reproducible case studies — metrics, interactive figures, published pipelines.",
  },
  {
    to: "/services",
    label: "services",
    line: "What I deliver, how engagements run, and the frameworks behind the work.",
  },
  {
    to: "/contact",
    label: "contact",
    line: "Availability, languages, timezone overlap — typical reply within 48 hours.",
  },
];

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

export function Home() {
  return (
    <>
      <section className="hero">
        <h1>Data Scientist &amp; ML Engineer</h1>
        <p className="hero-sub">
          I build ML/AI systems end to end — from data contracts and reproducible pipelines
          to measured evaluation and production deployment — and I keep the working code and
          case studies public. Location-independent; open to freelance and contract work.
        </p>
        <HeroTerminal />
        <p className="hero-cta">
          → open to engagements: <Link to="/contact">/contact</Link>
        </p>
      </section>

      <h2 className="section-title">where to go</h2>
      <div className="go-grid">
        {GO_LINKS.map((g) => (
          <Link key={g.to} to={g.to} className="go-card accent-card">
            <h3>$ {g.label} →</h3>
            <p>{g.line}</p>
          </Link>
        ))}
      </div>

      <p className="home-status">
        <span className="status-dot" aria-hidden="true" />
        available for engagements · <Link to="/contact">→ /contact</Link>
        <span className="status-note"> — typical reply within 48h</span>
      </p>
    </>
  );
}
