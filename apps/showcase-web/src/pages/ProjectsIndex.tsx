import { useEffect, useState } from "react";
import { getProjects, type Project } from "../api";
import { ProjectCard } from "../components/ProjectCard";

interface TopicGroup {
  topic: string;
  projects: Project[];
}

/** Group by topic; topics sorted by their earliest project, projects by order. */
export function groupByTopic(projects: Project[]): TopicGroup[] {
  const groups = new Map<string, Project[]>();
  for (const p of [...projects].sort((a, b) => a.order - b.order)) {
    const list = groups.get(p.topic) ?? [];
    list.push(p);
    groups.set(p.topic, list);
  }
  return [...groups.entries()].map(([topic, ps]) => ({ topic, projects: ps }));
}

/** Full project index: grouped by topic, with live key numbers per card. */
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
      {projects !== null &&
        groupByTopic(projects).map((g) => (
          <section key={g.topic} aria-label={g.topic}>
            <h2 className="section-title">{g.topic}</h2>
            <div className="project-grid">
              {g.projects.map((p) => (
                <ProjectCard key={p.id} project={p} />
              ))}
            </div>
          </section>
        ))}
    </>
  );
}
