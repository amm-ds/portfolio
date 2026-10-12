import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProjects, type Project } from "../api";
import { ProjectCard } from "../components/ProjectCard";
import { Terminal } from "../components/Terminal";
import { useTypedScript } from "../hooks/useTyped";

const HERO_SCRIPT = [
  { cmd: "whoami", output: "senior data scientist & ml/ai engineer" },
  { cmd: "dvc repro", output: "7 projects · 41.2M trips · 230+ tests · all green" },
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
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProjects()
      .then((list) => setProjects([...list].sort((a, b) => a.order - b.order)))
      .catch(() => setError("could not load the project index — is the API running?"));
  }, []);

  return (
    <>
      <section className="hero">
        <HeroTerminal />
        <p className="hero-cta">
          → open to freelance engagements: <Link to="/services">/services</Link>
        </p>
        <p className="hero-sub">
          This app is the live showcase of the public repository{" "}
          <a href="https://github.com/amm-ds/portfolio" target="_blank" rel="noreferrer">
            github.com/amm-ds/portfolio
          </a>{" "}
          — real pipelines, real metrics and interactive figures, served straight from the
          project artifacts.
        </p>
        <p className="availability">
          Available for freelance work — ML/AI systems, agentic AI and RAG, data engineering
          and MLOps. See the <Link to="/services">services</Link> page for offerings,
          process and engagement models.
        </p>
      </section>

      <h2 className="section-title">projects</h2>
      {error && <div className="state-box error">{error}</div>}
      {!error && projects === null && <p className="loading">loading projects…</p>}
      {projects !== null && (
        <div className="project-grid">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}
    </>
  );
}
