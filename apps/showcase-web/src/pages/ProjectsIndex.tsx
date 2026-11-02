import { useEffect, useState } from "react";
import { usePageMeta } from "../seo";
import {
  getDemoRegistry,
  getProjects,
  STATIC_PROJECTS,
  type DemoRegistryEntry,
  type Project,
} from "../api";
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

/** Row (section) definitions for the experiments block of the Projects page,
 * named after the services offerings and ordered by impact. Each row
 * aggregates one or more `topic` values from portfolio.yaml; the card keeps
 * its own domain and technique tags. Unmapped topics fall back to a row named
 * after themselves, so no card is ever dropped. */
export const TOPIC_ROWS: { name: string; description: string; topics: string[] }[] = [
  {
    name: "Agentic AI & LLM systems",
    description: "LLM agents with retrieval, tool use, and verification loops.",
    topics: ["Agentic AI & LLM"],
  },
  {
    name: "Machine learning",
    description:
      "Forecasting, anomaly detection, classification and decisioning with honest baselines.",
    topics: [
      "Forecasting & Time Series",
      "Anomaly Detection",
      "NLP & Transformers",
      "ML Systems & Decisioning",
      "Decision Science",
    ],
  },
  {
    name: "Optimization",
    description: "Routing and scheduling under real operational constraints.",
    topics: ["Optimization"],
  },
  {
    name: "APIs & model serving",
    description: "Measured latency and throughput trade-offs across serving stacks.",
    topics: ["Inference & Serving"],
  },
  {
    name: "Data engineering",
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

/** Anchor id for a topic row: "Agentic AI & LLM systems" → "agentic-ai-llm-systems". */
export function rowAnchor(name: string): string {
  return name
    .toLowerCase()
    .replace(/&/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Demo card content, from the live registry or the static fallback list. */
function DemoCard({
  title,
  line,
  href,
  hero,
}: {
  title: string;
  line: string;
  href?: string;
  hero?: DemoRegistryEntry["hero"];
}) {
  return (
    <div className="demo-card" aria-label={title}>
      <h3>{title}</h3>
      <p>{line}</p>
      {hero && (
        <p className="demo-hero">
          {hero.label}: {hero.value}
          {hero.ci ? ` — ${hero.ci}` : ""}
        </p>
      )}
      {href ? (
        <a className="demo-link" href={href}>
          open demo →
        </a>
      ) : null}
    </div>
  );
}

/** Demos block rendered above the topic rows. Cards come from the demo registry
 * (`GET /demos`) and render as a single row that scrolls horizontally on
 * overflow; on any fetch failure the static `DEMOS` list is rendered instead
 * (it doubles as the loading state). */
function DemosSection() {
  const [entries, setEntries] = useState<DemoRegistryEntry[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoRegistry()
      .then((list) => !cancelled && setEntries(list))
      .catch(() => !cancelled && setEntries(null));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="demos" id="demos" aria-label="Live demos">
      <h2 className="section-title">live demos</h2>
      <p className="section-intro">{DEMOS_INTRO}</p>
      {entries === null ? (
        <div className="demo-grid">
          {DEMOS.map((d) => (
            <DemoCard key={d.id} title={d.title} line={d.line} href={d.href} />
          ))}
        </div>
      ) : (
        <div className="demo-grid">
          {entries.map((d) => (
            <DemoCard key={d.id} title={d.title} line={d.hook} href={d.href} hero={d.hero} />
          ))}
        </div>
      )}
    </section>
  );
}

/** Projects index: a "live demos" block on top, then an "experiments" block
 * with offering-named topic rows as full-width sections and their cards in a
 * responsive 2-column grid. Both blocks live inside /projects (`/experiments`
 * is an alias).
 *
 * Resilience: if GET /projects fails we probe GET /demos — only when both are
 * unreachable do we conclude the registry is down and render the last
 * published snapshot (STATIC_PROJECTS, baked at build time), with a Retry
 * button that re-fetches. A /projects failure with a live /demos endpoint
 * keeps the plain error state. */
export function ProjectsIndex() {
  usePageMeta({
    title: "Demos & Experiments",
    description:
      "Interactive ML demos and reproducible experiment case studies — forecasting, churn, RAG, optimization and serving.",
  });
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setProjects(null);
    setError(null);
    setSnapshot(false);
    getProjects()
      .then((list) => !cancelled && setProjects([...list].sort((a, b) => a.order - b.order)))
      .catch(() => {
        if (cancelled) return;
        getDemoRegistry()
          .then(
            () =>
              !cancelled &&
              setError("could not load the project index — is the API running?"),
          )
          .catch(() => {
            if (cancelled) return;
            setSnapshot(true);
            setProjects([...STATIC_PROJECTS].sort((a, b) => a.order - b.order));
          });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const rows = projects !== null ? groupByRow(projects) : [];

  return (
    <>
      <h1 className="page-title">projects</h1>
      <p className="section-intro">
        Ten public experiments with live demos — real datasets, measured baselines and
        published pipelines. Every number on this page can be re-run from the repository.
      </p>
      <nav className="page-index" aria-label="On this page">
        <span className="page-index-label">index</span>
        <a href="#demos">live demos</a>
        {rows.map((row) => (
          <a key={row.name} href={`#${rowAnchor(row.name)}`}>
            {row.name}
          </a>
        ))}
      </nav>
      {snapshot && (
        <div className="state-box error" role="alert">
          The live registry is unreachable — showing the last published snapshot.{" "}
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            Retry
          </button>
        </div>
      )}
      {error && <div className="state-box error">{error}</div>}
      {!error && !snapshot && projects === null && <p className="loading">loading projects…</p>}
      {projects !== null && projects.length === 0 && (
        <div className="state-box">No projects published yet — check back soon.</div>
      )}
      <DemosSection />
      {projects !== null && projects.length > 0 && (
        <div className="experiments-block" id="experiments">
          <h2 className="section-title">experiments</h2>
          <p className="section-intro">
            Ten reproducible case studies grouped by discipline — each card states the
            objective, the data and the result.
          </p>
          <div className="topic-rows">
            {rows.map((row) => (
              <section
                key={row.name}
                id={rowAnchor(row.name)}
                className="topic-row"
                aria-label={row.name}
              >
                <h3 className="section-title">{row.name}</h3>
                {row.description && <p className="section-intro">{row.description}</p>}
                <div className="project-grid">
                  {row.topics.flatMap((t) =>
                    t.projects.map((p) => <ProjectCard key={p.id} project={p} />),
                  )}
                </div>
              </section>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
