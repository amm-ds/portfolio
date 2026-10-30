// Typed fetch wrappers for the showcase API (root-relative paths; the Vite dev
// server proxies these to the FastAPI backend, which serves them + dist/ in prod).

export interface Project {
  id: string;
  title: string;
  domain: string;
  /** Display grouping key for the projects index. */
  topic: string;
  techniques: string[];
  data: string;
  status: "flagship" | "working" | "planned";
  order: number;
}

export type Metrics = Record<string, Record<string, unknown>>;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new ApiError(path, res.status);
  }
  return (await res.json()) as T;
}

export class ApiError extends Error {
  constructor(
    public readonly path: string,
    public readonly status: number,
  ) {
    super(`request to ${path} failed with ${status}`);
    this.name = "ApiError";
  }
}

export function getProjects(): Promise<Project[]> {
  return getJson<Project[]>("/projects");
}

/** 404 means "pipeline not run yet" — callers treat it as empty. */
export async function getMetrics(projectId: string): Promise<Metrics | null> {
  try {
    return await getJson<Metrics>(`/projects/${projectId}/metrics`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

// --- Case-study stories --------------------------------------------------------

export interface StorySectionData {
  id: string;
  title: string;
  text_md: string;
  figures: string[];
  metrics_keys: string[];
}

export interface RoadmapItemData {
  status: "delivered" | "remaining" | "deferred";
  text: string;
}

export interface ProjectStoryData {
  project_id: string;
  /** Headline result with its uncertainty, when authored. */
  headline?: string | null;
  /** Data provenance, size and licensing note. */
  data_note?: string | null;
  /** What the case study does not establish. */
  limits?: string | null;
  /** Single plain-text source for card/README/docs/SEO/social short copy. */
  short_version?: string | null;
  sections: StorySectionData[];
  /** Finalized roadmap (optional while stories are being authored). */
  roadmap?: RoadmapItemData[];
  /** Commentary per figure id, rendered as the footer under each chart. */
  figure_captions?: Record<string, string>;
}

/** 404 means "story not authored yet" — callers fall back to the raw artifacts view. */
export async function getStory(projectId: string): Promise<ProjectStoryData | null> {
  try {
    return await getJson<ProjectStoryData>(`/projects/${projectId}/story`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function getFigures(projectId: string): Promise<string[]> {
  return getJson<string[]>(`/projects/${projectId}/figures`);
}

export function figureUrl(projectId: string, name: string): string {
  return `/projects/${projectId}/figures/${name}`;
}

// --- Interactive demos ---------------------------------------------------------

// Demo platform types live in ./demos/types (mirror of portfolio_core.demo);
// re-exported here so API callers have a single import site.
import type { DemoManifest, DemoRegistryEntry } from "./demos/types";

export type {
  DemoManifest,
  DemoRegistryEntry,
  HeroMetric,
  LiveEndpoint,
  PayloadRef,
  Scenario,
} from "./demos/types";

/** Live demo registry served by the API; falls back to the static list on error. */
export function getDemoRegistry(): Promise<DemoRegistryEntry[]> {
  return getJson<DemoRegistryEntry[]>("/demos");
}

// --- Static snapshot (last resort) ---------------------------------------------
// Baked at build time by scripts/gen_static_registry.py from the same YAML the
// API serves (projects/*/portfolio.yaml + story.yaml + demo.yaml). The projects
// index renders from it when both GET /projects and GET /demos are unreachable;
// per-endpoint fallbacks (static demo cards, error boxes) stay in place before
// this kicks in.
export {
  STATIC_DEMO_REGISTRY,
  STATIC_PROJECTS,
  STATIC_STORIES,
} from "./lib/staticRegistry";

export function getDemoManifest(demoId: string): Promise<DemoManifest> {
  return getJson<DemoManifest>(`/demos/${demoId}/manifest`);
}

/** Precomputed lookup data for an interactive demo (`/demos/{demo_id}/payload`). */
export function getDemoPayload<T>(demoId: string): Promise<T> {
  return getJson<T>(`/demos/${demoId}/payload`);
}

export interface ChurnScoreResult {
  churn_probability: number;
  decision: {
    alarm: boolean;
    threshold: number;
    expected_cost_note: string;
  };
}

/** Live scoring for the churn demo; 503 means serving artifacts are not built. */
export async function scoreChurn(
  projectId: string,
  features: Record<string, number | string>,
): Promise<ChurnScoreResult> {
  const path = `/projects/${projectId}/score`;
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
  });
  if (!res.ok) {
    throw new ApiError(path, res.status);
  }
  return (await res.json()) as ChurnScoreResult;
}
