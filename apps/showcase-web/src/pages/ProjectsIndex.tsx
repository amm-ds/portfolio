import { useEffect, useState } from "react";
import { getProjects, type Project } from "../api";
import { ProjectCard } from "../components/ProjectCard";
import { DEMOS, DEMOS_INTRO } from "../lib/demos";

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

/** Row (section) definitions for the Experiments page, in display order by
 * impact. Each row aggregates one or more `topic` values from portfolio.yaml;
 * the card keeps its own topic as a sub-topic chip. Unmapped topics fall back
 * to a row named after themselves, so no card is ever dropped. */
export const TOPIC_ROWS: { name: string; description: string; topics: string[] }[] = [
  {
    name: "Agentic AI & LLM",
    description: "LLM agents with retrieval, tool use, and verification loops.",
    topics: ["Agentic AI & LLM"],
  },
  {
    name: "Machine Learning",
    description: "Forecasting, anomaly detection, and classification with honest baselines.",
    topics: [
      "Forecasting & Time Series",
      "Anomaly Detection",
      "NLP & Transformers",
      "ML Systems & Decisioning",
    ],
  },
  {
    name: "Optimization",
    description: "Routing and scheduling under real operational constraints.",
    topics: ["Optimization"],
  },
  {
    name: "Inference & Serving",
    description: "Measured latency/throughput trade-offs across serving stacks.",
    topics: ["Inference & Serving"],
  },
  {
    name: "Decision Science",
    description: "Causal inference and uplift modeling for decision policies.",
    topics: ["Decision Science"],
  },
  {
    name: "Data Engineering",
    description: "Reproducible pipelines over large open datasets with quality gates.",
    topics: ["Data Engineering", "Large-Scale Data Engineering"],
  },
];

export interface TopicRow {
  name: string;
  description: string;
  topics: TopicGroup[];
}

/** Compose groupByTopic into row sections; empty rows are dropped and
 * unmapped topics become their own trailing rows. Projects keep their order
 * within a row, so cards never straddle sections. */
export function groupByRow(projects: Project[]): TopicRow[] {
  const topicGroups = groupByTopic(projects);
  const mapped = new Set(TOPIC_ROWS.flatMap((r) => r.topics));
  const rows: TopicRow[] = TOPIC_ROWS.map((r) => ({
    name: r.name,
    description: r.description,
    topics: topicGroups.filter((t) => r.topics.includes(t.topic)),
  })).filter((r) => r.topics.length > 0);
  const extras = topicGroups
    .filter((t) => !mapped.has(t.topic))
    .map((t) => ({ name: t.topic, description: "", topics: [t] }));
  return [...rows, ...extras];
}

/** Placeholder demos rendered above the topic rows; real demos drop in via lib/demos.ts. */
function DemosSection() {
  return (
    <section className="demos" aria-label="Demos">
      <h2 className="section-title">Demos — interactive experiments</h2>
      <p className="section-intro">{DEMOS_INTRO}</p>
      <div className="demo-grid">
        {DEMOS.map((d) => (
          <div key={d.id} className="demo-card" aria-label={`${d.title} (coming soon)`}>
            <h3>{d.title}</h3>
            <p>{d.line}</p>
            <span className="chip demo-status">{d.status}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Experiments index: demos placeholder on top, then topic rows as full-width
 * sections with their cards in a responsive 2-column grid. */
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
      <h1 className="page-title">experiments</h1>
      {error && <div className="state-box error">{error}</div>}
      {!error && projects === null && <p className="loading">loading projects…</p>}
      {projects !== null && projects.length === 0 && (
        <div className="state-box">No projects published yet — check back soon.</div>
      )}
      <DemosSection />
      {projects !== null && projects.length > 0 && (
        <div className="topic-rows">
          {groupByRow(projects).map((row) => (
            <section key={row.name} className="topic-row" aria-label={row.name}>
              <h2 className="section-title">{row.name}</h2>
              {row.description && <p className="section-intro">{row.description}</p>}
              <div className="project-grid">
                {row.topics.flatMap((t) =>
                  t.projects.map((p) => <ProjectCard key={p.id} project={p} />),
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
