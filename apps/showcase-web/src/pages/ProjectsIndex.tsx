import { useEffect, useState } from "react";
import { getProjects, type Project } from "../api";
import { ProjectCard } from "../components/ProjectCard";

function Group({ title, projects }: { title: string; projects: Project[] }) {
  if (projects.length === 0) return null;
  return (
    <>
      <h2 className="section-title">{title}</h2>
      <div className="project-grid">
        {projects.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </>
  );
}

/** Full project index: flagships and working showcases, with live key numbers. */
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
      {error && <div className="state-box error">{error}</div>}
      {!error && projects === null && <p className="loading">loading projects…</p>}
      {projects !== null && projects.length === 0 && (
        <div className="state-box">No projects published yet — check back soon.</div>
      )}
      {projects !== null && projects.length > 0 && (
        <>
          <Group title="flagships" projects={projects.filter((p) => p.status === "flagship")} />
          <Group
            title="working showcases"
            projects={projects.filter((p) => p.status === "working")}
          />
        </>
      )}
    </>
  );
}
