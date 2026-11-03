import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { usePageMeta } from "../seo";
import {
  getDemoRegistry,
  getProjects,
  STATIC_PROJECTS,
  type DemoRegistryEntry,
  type Project,
} from "../api";
import { ProjectCard } from "../components/ProjectCard";
import { StudyCard } from "../components/StudyCard";
import { cardTags } from "../lib/cardCopy";
import { DEMOS, DEMOS_INTRO, demoDoes } from "../lib/demos";

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

/** Display fields a demo card needs — served live by the registry, mirrored
 * by the static fallback (lib/demos.ts). */
interface DemoCardData {
  id: string;
  title: string;
  hook: string;
  href?: string;
  /** One-line domain descriptor, e.g. "plan operations". */
  group?: string;
  /** Linked experiment id — its four card tags tag the demo card. */
  project?: string;
  /** Headline metric (label/value) for the card's "results" block. */
  hero?: DemoRegistryEntry["hero"] | null;
}

/** Demo cards reuse the linked experiment's four card tags, so both card
 * kinds share one tag vocabulary. */
function demoTags(projectId: string | undefined): string[] {
  return cardTags(projectId ?? "", []).slice(0, 4);
}

/** One-line "results" block for a demo card, from the registry's headline
 * metric ("decision cost per 1,400 customers: $601 vs $1,035 naive") — the
 * value renders in the accent metric style. Demos without a published
 * metric render no results block. */
function demoResults(data: DemoCardData): ReactNode {
  const hero = data.hero;
  if (!hero) return undefined;
  return (
    <>
      {hero.label}: <span className="study-metric">{hero.value}</span>
    </>
  );
}

/** Demo card on the projects index: the SAME study-card layout as the
 * experiment cards, fed from the demo registry (or the static fallback):
 * title; use-case/domain metadata; the labeled "description" block and, when
 * the registry publishes one, the labeled "results" block with the headline
 * metric; exactly four tags. */
function DemoCard({ data, domain }: { data: DemoCardData; domain?: string }) {
  const meta = [
    ...(data.group ? [{ label: "use case", value: data.group }] : []),
    ...(domain ? [{ label: "domain", value: domain }] : []),
  ];
  const body = (
    <StudyCard
      title={data.title}
      meta={meta}
      doesLabel="description"
      does={demoDoes(data)}
      achievesLabel="results"
      achieves={demoResults(data)}
      tags={demoTags(data.project)}
    />
  );
  return data.href ? (
    <Link to={data.href} className="demo-card study-card">
      {body}
    </Link>
  ) : (
    <div className="demo-card study-card" aria-label={data.title}>
      {body}
    </div>
  );
}

/** Demos block rendered above the experiments rows — one of the two big page
 * sections. Cards come from the demo registry (`GET /demos`) and render in a
 * full-width grid like the experiment cards below; on any fetch failure the
 * static `DEMOS` list is rendered instead (it doubles as the loading state).
 * The linked experiment's domain joins the use case in the metadata. */
function DemosSection({ projects }: { projects: Project[] | null }) {
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

  const domainOf = (projectId: string | undefined) =>
    projects?.find((p) => p.id === projectId)?.domain;

  return (
    <section className="demos" id="demos" aria-label="Live demos">
      <h2 className="section-title section-title--major">live demos</h2>
      <p className="section-intro">{DEMOS_INTRO}</p>
      {entries === null ? (
        <div className="demo-grid">
          {DEMOS.map((d) => (
            <DemoCard
              key={d.id}
              data={{
                id: d.id,
                title: d.title,
                hook: d.line,
                href: d.href,
                group: d.group,
                project: d.project,
                hero: d.hero,
              }}
              domain={domainOf(d.project)}
            />
          ))}
        </div>
      ) : (
        <div className="demo-grid">
          {entries.map((d) => (
            <DemoCard key={d.id} data={d} domain={domainOf(d.project)} />
          ))}
        </div>
      )}
    </section>
  );
}

/** Projects index: "live demos" and "experiments" are the two big page
 * sections; inside experiments, offering-domain rows are subordinate group
 * labels with their cards in a responsive 2-column grid. Both blocks live
 * inside /projects (`/experiments` is an alias).
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
        A growing set of public, reproducible case studies with live demos — real datasets,
        measured baselines and published pipelines. Every number on this page can be re-run
        from the repository.
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
      <DemosSection projects={projects} />
      {projects !== null && projects.length > 0 && (
        <div className="experiments-block" id="experiments">
          <h2 className="section-title section-title--major">experiments</h2>
          <p className="section-intro">
            A growing set of reproducible case studies grouped by discipline — each card
            states the objective, the data and the result. Terms are defined in the{" "}
            <Link to="/glossary">glossary</Link>.
          </p>
          <div className="topic-rows">
            {rows.map((row) => (
              <section
                key={row.name}
                id={rowAnchor(row.name)}
                className="topic-row"
                aria-label={row.name}
              >
                <h3 className="row-label">{row.name}</h3>
                {row.description && <p className="row-desc">{row.description}</p>}
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
