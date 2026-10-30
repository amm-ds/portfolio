import { Link } from "react-router-dom";
import { AVAILABILITY } from "../config";
import { PersonJsonLd, usePageMeta } from "../seo";
import { Terminal } from "../components/Terminal";
import { useTypedScript } from "../hooks/useTyped";

export const HERO_SCRIPT = [
  { cmd: "whoami", output: "data scientist · ml & ai consultant" },
  { cmd: "focus", output: "agentic ai · forecasting · machine learning · optimization · data engineering" },
  { cmd: "stack", output: "pydantic-ai · pytorch · polars · scikit-learn · plotly · dvc" },
  { cmd: "principles", output: "reproducible pipelines · honest baselines · production-grade code" },
];

/** The terminal's fully-typed content, kept in the DOM from first render as
 * the accessible name of the (aria-hidden) animated copy. */
const HERO_MESSAGE = HERO_SCRIPT.map((l) => `$ ${l.cmd}\n${l.output ?? ""}`).join("\n");

const GO_LINKS = [
  {
    to: "/projects",
    label: "projects",
    line: "10 reproducible experiments — metrics, interactive figures, published pipelines.",
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
    <div role="img" aria-label={HERO_MESSAGE} className="hero-terminal">
      {/* Animated copy is decorative; the full message above is what AT reads. */}
      <div aria-hidden="true">
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
      </div>
    </div>
  );
}

export function Home() {
  usePageMeta({
    title: "Data Scientist, ML & AI Consultant",
    description:
      "Applied AI, predictive analytics and ML engineering — reproducible experiments with measured baselines, published code, and honest case studies.",
  });

  return (
    <>
      <PersonJsonLd />
      <section className="hero">
        <h1>Data Scientist, ML &amp; AI Consultant</h1>
        <p className="hero-kicker">
          applied AI, predictive analytics and ML engineering — from experiment to production
        </p>
        <p className="hero-sub">
          I design, build and evaluate ML systems end to end, and I keep the code, metrics and
          case studies public so the results can be checked before you reach out.
        </p>
        <HeroTerminal />
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
        {AVAILABILITY.status} · <Link to="/contact">→ /contact</Link>
        <span className="status-note"> — typical reply within {AVAILABILITY.replyHours}h</span>
      </p>
    </>
  );
}
