import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProjects, type Project } from "../api";
import { ProjectCard } from "../components/ProjectCard";
/** Full project index — the grid moved here from Home in wave 4. */
export function ProjectsIndex() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProjects()
      .then((list) => setProjects([...list].sort((a, b) => a.order - b.order)))
      .catch(() => setError("could not load the project index — is the API running?"));
  }, []);

  return (
    <>
      <h1 className="page-title">projects</h1>
      <Link to="/chat" className="demo-banner">
        <span className="demo-label">[live demo]</span> RAG demo — ask the portfolio's own
        agent about project 01, streaming with citations →
      </Link>
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
