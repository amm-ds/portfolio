// Typed fetch wrappers for the showcase API (root-relative paths; the Vite dev
// server proxies these to the FastAPI backend, which serves them + dist/ in prod).

import type { DemoManifest, DemoRegistryEntry } from "./demos/types";

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
type Validator<T> = (value: unknown) => value is T;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function hasStrings(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => typeof value[key] === "string");
}

function hasNumbers(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => isNumber(value[key]));
}

async function getJson<T>(
  path: string,
  validate: Validator<T>,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) throw new ApiError(path, res.status);
  const data: unknown = await res.json();
  if (!validate(data)) throw new Error(`invalid response contract from ${path}`);
  return data;
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

function isProject(value: unknown): value is Project {
  return (
    isRecord(value) &&
    hasStrings(value, ["id", "title", "domain", "topic", "data", "status"]) &&
    ["flagship", "working", "planned"].includes(value.status as string) &&
    isStringArray(value.techniques) &&
    isNumber(value.order)
  );
}

export function getProjects(signal?: AbortSignal): Promise<Project[]> {
  return getJson("/projects", (value): value is Project[] =>
    Array.isArray(value) && value.every(isProject), signal);
}

export interface ProjectHeadline {
  metric: string;
  value: number;
}

function isProjectHeadline(value: unknown): value is ProjectHeadline {
  return isRecord(value) && hasStrings(value, ["metric"]) && hasNumbers(value, ["value"]);
}

/** Compact card headlines, selected by the API from each project's metrics. */
export function getProjectHeadlines(
  signal?: AbortSignal,
): Promise<Record<string, ProjectHeadline>> {
  return getJson("/projects/headlines", (value): value is Record<string, ProjectHeadline> =>
    isRecord(value) && Object.values(value).every(isProjectHeadline), signal);
}

/** 404 means "pipeline not run yet" — callers treat it as empty. */
export async function getMetrics(projectId: string, signal?: AbortSignal): Promise<Metrics | null> {
  try {
    return await getJson(
      `/projects/${projectId}/metrics`,
      (value): value is Metrics => isRecord(value) && Object.values(value).every(isRecord),
      signal,
    );
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
  /** Ideas that arose, rendered as a card in the Background section. */
  key_concepts?: string[];
  /** Commentary per figure id, rendered as the footer under each chart. */
  figure_captions?: Record<string, string>;
}

function isStorySection(value: unknown): value is StorySectionData {
  return (
    isRecord(value) &&
    hasStrings(value, ["id", "title", "text_md"]) &&
    isStringArray(value.figures) &&
    isStringArray(value.metrics_keys)
  );
}

function isOptionalNullableString(value: Record<string, unknown>, key: string): boolean {
  return value[key] === undefined || value[key] === null || typeof value[key] === "string";
}

function isStory(value: unknown): value is ProjectStoryData {
  if (!isRecord(value) || !hasStrings(value, ["project_id"]) || !Array.isArray(value.sections)) {
    return false;
  }
  if (!value.sections.every(isStorySection)) return false;
  if (!["headline", "data_note", "limits", "short_version"].every((key) =>
    isOptionalNullableString(value, key))) return false;
  if (value.key_concepts !== undefined && !isStringArray(value.key_concepts)) return false;
  if (value.figure_captions !== undefined && !(
    isRecord(value.figure_captions) &&
    Object.values(value.figure_captions).every((caption) => typeof caption === "string")
  )) return false;
  return value.roadmap === undefined || (
    Array.isArray(value.roadmap) && value.roadmap.every((item) =>
      isRecord(item) &&
      hasStrings(item, ["status", "text"]) &&
      ["delivered", "remaining", "deferred"].includes(item.status as string))
  );
}

/** 404 means "story not authored yet" — callers fall back to the raw artifacts view. */
export async function getStory(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectStoryData | null> {
  try {
    return await getJson(`/projects/${projectId}/story`, isStory, signal);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function getFigures(projectId: string, signal?: AbortSignal): Promise<string[]> {
  return getJson(`/projects/${projectId}/figures`, isStringArray, signal);
}

export function figureUrl(projectId: string, name: string): string {
  return `/projects/${projectId}/figures/${name}`;
}

// --- Interactive demos ---------------------------------------------------------

export type { DemoRegistryEntry } from "./demos/types";

function isHero(value: unknown): boolean {
  return value === null || (
    isRecord(value) &&
    hasStrings(value, ["label", "value"]) &&
    (value.ci === undefined || value.ci === null || typeof value.ci === "string")
  );
}

function isDemoRegistryEntry(value: unknown): value is DemoRegistryEntry {
  return isRecord(value) &&
    hasStrings(value, ["id", "title", "hook", "group", "href", "project", "status"]) &&
    isHero(value.hero);
}

/** Live demo registry served by the API; falls back to the static list on error. */
export function getDemoRegistry(signal?: AbortSignal): Promise<DemoRegistryEntry[]> {
  return getJson("/demos", (value): value is DemoRegistryEntry[] =>
    Array.isArray(value) && value.every(isDemoRegistryEntry), signal);
}

// --- Static snapshot (last resort) ---------------------------------------------
// Baked at build time by scripts/gen_static_registry.py from the same YAML the
// API serves (projects/*/portfolio.yaml + story.yaml + demo.yaml). Each page
// section owns its fallback: a project-index failure never depends on /demos.
export {
  STATIC_DEMO_REGISTRY,
  STATIC_PROJECTS,
} from "./lib/staticRegistry";

function isDemoManifest(value: unknown): value is DemoManifest {
  if (!isRecord(value) ||
    !hasStrings(value, ["id", "title", "hook", "project", "group"]) ||
    !isStringArray(value.skills) || !isStringArray(value.modes) || !isHero(value.hero)) {
    return false;
  }
  if (!Array.isArray(value.scenarios) || !value.scenarios.every((scenario) =>
    isRecord(scenario) && hasStrings(scenario, ["name"]) && isRecord(scenario.controls) &&
    Object.values(scenario.controls).every((control) =>
      ["number", "string", "boolean"].includes(typeof control)))) return false;
  if (!Array.isArray(value.live_endpoints) || !value.live_endpoints.every((endpoint) =>
    isRecord(endpoint) && hasStrings(endpoint, ["method", "path", "label", "cost"]) &&
    ["GET", "POST"].includes(endpoint.method as string))) return false;
  return value.payload === null || (
    isRecord(value.payload) && hasStrings(value.payload, ["path"]) &&
    isStringArray(value.payload.required_keys) &&
    Number.isInteger(value.payload.schema_version)
  );
}

export function getDemoManifest(demoId: string, signal?: AbortSignal): Promise<DemoManifest> {
  return getJson(`/demos/${demoId}/manifest`, isDemoManifest, signal);
}

/** Raw payload JSON; each demo loader applies its own versioned nested contract. */
export function getDemoPayload(demoId: string, signal?: AbortSignal): Promise<unknown> {
  return getJson(`/demos/${demoId}/payload`, (_value): _value is unknown => true, signal);
}

export interface ChurnScoreResult {
  churn_probability: number;
  decision: {
    alarm: boolean;
    threshold: number;
    expected_cost_note: string;
  };
}

function isChurnScoreResult(value: unknown): value is ChurnScoreResult {
  return isRecord(value) && hasNumbers(value, ["churn_probability"]) &&
    isRecord(value.decision) && hasNumbers(value.decision, ["threshold"]) &&
    hasStrings(value.decision, ["expected_cost_note"]) &&
    typeof value.decision.alarm === "boolean";
}

/** Live scoring for the churn demo; 503 means serving artifacts are not built. */
export async function scoreChurn(
  projectId: string,
  features: Record<string, number | string>,
  signal?: AbortSignal,
): Promise<ChurnScoreResult> {
  const path = `/projects/${projectId}/score`;
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
    signal,
  });
  if (!res.ok) throw new ApiError(path, res.status);
  const data: unknown = await res.json();
  if (!isChurnScoreResult(data)) throw new Error(`invalid response contract from ${path}`);
  return data;
}

// --- Contact phone gate -------------------------------------------------------
// The direct phone line never ships in the client bundle; it is returned only
// by this endpoint, once, after one deliberate step.

export interface ContactUnlockResult {
  phone: string;
}

/** 503 means the deployment has no CONTACT_PHONE configured. */
export async function unlockContactPhone(value: string): Promise<ContactUnlockResult> {
  const path = "/contact/unlock";
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) throw new ApiError(path, res.status);
  const data: unknown = await res.json();
  if (!isRecord(data) || typeof data.phone !== "string") {
    throw new Error(`invalid response contract from ${path}`);
  }
  return { phone: data.phone };
}
