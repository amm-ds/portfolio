import { useEffect, useState } from "react";
import { getProjects, type Project } from "../api";
import { ProjectCard } from "../components/ProjectCard";

export interface TopicGroup {
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

/** Umbrella → topics mapping, in display order (single source of truth). */
export const UMBRELLAS: { name: string; description: string; topics: string[] }[] = [
  {
    name: "AI",
    description: "Agents, retrieval systems, and transformer models.",
    topics: ["Agentic AI & LLM", "NLP & Transformers"],
  },
  {
    name: "Machine Learning",
    description: "Forecasting, detection, decisioning, and optimization.",
    topics: [
      "Forecasting & Time Series",
      "Anomaly Detection",
      "ML Systems & Decisioning",
      "Optimization",
    ],
  },
  {
    name: "Data Engineering",
    description: "Pipelines over large open datasets.",
    topics: ["Large-Scale Data Engineering"],
  },
];

export interface UmbrellaGroup {
  name: string;
  description: string;
  topics: TopicGroup[];
}

/** Compose groupByTopic into umbrella sections; empty umbrellas are dropped. */
export function groupByUmbrella(projects: Project[]): UmbrellaGroup[] {
  const topicGroups = groupByTopic(projects);
  return UMBRELLAS.map((u) => ({
    name: u.name,
    description: u.description,
    topics: topicGroups.filter((t) => u.topics.includes(t.topic)),
  })).filter((u) => u.topics.length > 0);
}

/** Full project index: umbrella sections → topic subgroups → responsive card grid. */
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
        <div className="umbrellas">
          {groupByUmbrella(projects).map((u) => (
            <section key={u.name} className="umbrella" aria-label={u.name}>
              <h2 className="section-title">{u.name}</h2>
              <p className="section-intro">{u.description}</p>
              {u.topics.map((t) => (
                <div key={t.topic} className="topic-group">
                  {u.topics.length > 1 && <h3 className="topic-title">{t.topic}</h3>}
                  <div className="project-grid">
                    {t.projects.map((p) => (
                      <ProjectCard key={p.id} project={p} />
                    ))}
                  </div>
                </div>
              ))}
            </section>
          ))}
        </div>
      )}
    </>
  );
}
