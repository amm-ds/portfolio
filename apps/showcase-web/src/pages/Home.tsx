import { Link } from "react-router-dom";
import { AVAILABILITY, SITE_NAME } from "../config";
import { usePageMeta } from "../seo";
import { Terminal } from "../components/Terminal";
import { useTypedScript } from "../hooks/useTyped";

export const HERO_SCRIPT = [
  { cmd: "whoami", output: "data scientist · ml & ai consultant" },
  {
    cmd: "focus",
    output:
      "artificial intelligence · machine learning · optimization · data engineering · mlops · full-stack engineering",
  },
  { cmd: "stack", output: "python · typescript/react · pytorch · lightgbm · scikit-learn · pydantic-ai · ollama · docker · dvc · uv" },
  {
    cmd: "principles",
    output: "reproducible pipelines · honest baselines · production-grade code · results quality & performance first",
  },
];

/** The terminal's fully-typed content, kept in the DOM from first render as
 * the accessible name of the (aria-hidden) animated copy. */
const HERO_MESSAGE = HERO_SCRIPT.map((l) => `> ${l.cmd}\n${l.output ?? ""}`).join("\n");

const GO_LINKS = [
  {
    to: "/projects",
    label: "projects",
    line: "a growing set of reproducible experiments — metrics, interactive figures, published pipelines.",
  },
  {
    to: "/services",
    label: "services",
    line: "What I deliver, how engagements run, and the frameworks behind the work.",
  },
  {
    to: "/contact",
    label: "contact",
    line: `Availability, languages, timezone overlap — replies within ${AVAILABILITY.replyHours}h on business days.`,
  },
];

function HeroTerminal() {
  const { lines, currentCmd, done } = useTypedScript(HERO_SCRIPT);
  const title = `alejandro@${SITE_NAME}: ~`;
  return (
    <div role="img" aria-label={HERO_MESSAGE} className="hero-terminal">
      {/* Animated copy is decorative; the full message above is what AT reads. */}
      <div aria-hidden="true" className="hero-terminal-stage">
        {/* Sizer: the full script rendered at final size reserves the layout
           box, so the typing animation fills a static terminal instead of
           growing the panel and pushing "where to go" down the page. */}
        <div className="hero-terminal-sizer">
          <Terminal title={title}>
            {HERO_SCRIPT.map((line, i) => (
              <div key={i}>
                <p className="cmd">{line.cmd}</p>
                {line.output && <p className="out">{line.output}</p>}
              </div>
            ))}
            <p className="cmd-partial">
              <span className="cursor" aria-hidden="true" />
            </p>
          </Terminal>
        </div>
        <div className="hero-terminal-live">
          <Terminal title={title}>
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
      <section className="hero">
        <h1>
          <span className="hero-accent">Data</span> Scientist, <span className="hero-accent">ML</span>{" "}
          &amp; <span className="hero-accent">AI</span> Consultant
        </h1>
        <p className="hero-sub">
          I design and build predictive systems, intelligent applications and data platforms —
          from first experiment to reliable production deployment.
        </p>
        <div className="hero-tags">
          <span className="chip">Predictive analytics &amp; forecasting</span>
          <span className="chip">Applied AI, RAG &amp; agentic systems</span>
          <span className="chip">ML engineering &amp; production infrastructure</span>
        </div>
        <p className="meta-links" style={{ justifyContent: "center", margin: "1.1rem 0 0" }}>
          <Link className="chip-link" to="/contact">
            Discuss a project →
          </Link>
          <Link className="chip-link" to="/projects">
            Explore the work →
          </Link>
        </p>
        <HeroTerminal />
      </section>

      <h2 className="section-title section-title--tight home-where-to-go">where to go</h2>
      <div className="go-grid">
        {GO_LINKS.map((g) => (
          <Link key={g.to} to={g.to} className="go-card accent-card">
            <h3>&gt; {g.label} →</h3>
            <p>{g.line}</p>
          </Link>
        ))}
      </div>

      <p className="home-status">
        <span className="status-dot" aria-hidden="true" />
        {AVAILABILITY.status} · <Link to="/contact">→ /contact</Link>
        <span className="status-note"> — replies within {AVAILABILITY.replyHours}h</span>
      </p>
    </>
  );
}
