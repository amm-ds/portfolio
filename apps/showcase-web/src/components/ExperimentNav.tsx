import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { Project } from "../api";

export interface ExperimentNavProps {
  /** Current experiment id (the :id route param). */
  projectId: string;
  /** /projects registry payload; the component sorts by `order` for sequence. */
  projects: Project[];
}

interface Neighbors {
  current?: Project;
  prev?: Project;
  next?: Project;
}

/** Registry-order (ascending `order`) neighbors around the current project. */
function neighbors(projectId: string, projects: Project[]): Neighbors {
  const sorted = [...projects].sort((a, b) => a.order - b.order);
  const idx = sorted.findIndex((p) => p.id === projectId);
  if (idx < 0) return {};
  return {
    current: sorted[idx],
    prev: idx > 0 ? sorted[idx - 1] : undefined,
    next: idx < sorted.length - 1 ? sorted[idx + 1] : undefined,
  };
}

const mono: CSSProperties = { fontFamily: "var(--mono)" };
const crumbsStyle: CSSProperties = { ...mono, fontSize: "0.85rem", margin: "0 0 1rem" };
const crumbSep: CSSProperties = { color: "var(--muted)", margin: "0 0.4rem" };
const pagerStyle: CSSProperties = {
  ...mono,
  display: "flex",
  justifyContent: "space-between",
  gap: "0.5rem",
  flexWrap: "wrap",
  margin: "2.5rem 0 0.5rem",
  fontSize: "0.88rem",
};

/** "Experiments / <project title>" breadcrumbs for the experiment page. */
export function ExperimentCrumbs({ projectId, projects }: ExperimentNavProps) {
  const { current } = neighbors(projectId, projects);
  if (!current) return null;
  return (
    <nav className="experiment-crumbs" aria-label="Breadcrumbs" style={crumbsStyle}>
      <Link to="/projects">Experiments</Link>
      <span style={crumbSep}>/</span>
      <Link to={`/projects/${current.id}`}>{current.title}</Link>
    </nav>
  );
}

/** Prev/next experiment pager in registry order; hides gracefully at the ends. */
export function ExperimentNav({ projectId, projects }: ExperimentNavProps) {
  const { prev, next } = neighbors(projectId, projects);
  if (!prev && !next) return null;
  return (
    <nav className="experiment-nav" aria-label="Experiments" style={pagerStyle}>
      {prev ? (
        <Link className="chip-link" to={`/projects/${prev.id}`}>
          ‹ prev · {prev.title}
        </Link>
      ) : (
        <span aria-hidden="true" />
      )}
      {next ? (
        <Link className="chip-link" to={`/projects/${next.id}`}>
          {next.title} · next ›
        </Link>
      ) : (
        <span aria-hidden="true" />
      )}
    </nav>
  );
}
