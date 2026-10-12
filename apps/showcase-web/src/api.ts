// Typed fetch wrappers for the showcase API (root-relative paths; the Vite dev
// server proxies these to the FastAPI backend, which serves them + dist/ in prod).

export interface Project {
  id: string;
  title: string;
  domain: string;
  techniques: string[];
  data: string;
  status: "flagship" | "working";
  order: number;
}

export type Metrics = Record<string, Record<string, unknown>>;

export interface Citation {
  chunk_id: string;
  article_id: string;
  title: string;
  excerpt: string;
  score: number;
}

export interface ChatResult {
  summary: string;
  citations: Citation[];
  confidence: number;
}

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
    super(`GET ${path} failed with ${status}`);
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

export interface ProjectStoryData {
  project_id: string;
  sections: StorySectionData[];
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

// --- SSE parsing (pure function, unit-tested) --------------------------------

export type SseEvent = { event: string; data: string };

/**
 * Parse a chunk of an SSE stream, returning the complete events it contains.
 * Handles partial lines/chunks via `remainder`: pass the returned remainder
 * back in with the next chunk. Handles multi-line `data:` payloads.
 */
export function parseSseChunk(chunk: string, remainder: string): {
  events: SseEvent[];
  remainder: string;
} {
  const buffer = remainder + chunk;
  const rawEvents = buffer.split(/\r?\n\r?\n/);
  const leftover = rawEvents.pop() ?? "";
  const events: SseEvent[] = [];
  for (const raw of rawEvents) {
    if (!raw.trim()) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of raw.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
    }
    if (dataLines.length > 0) events.push({ event, data: dataLines.join("\n") });
  }
  return { events, remainder: leftover };
}

// --- RAG chat streaming -------------------------------------------------------

export interface StreamHandlers {
  onDelta: (delta: string) => void;
  onResult: (result: ChatResult) => void;
  onError: (message: string) => void;
}

/**
 * POST /rag/chat/stream and read the SSE response. Calls `onDelta` for each
 * `text` event and `onResult` once with the parsed `result` event payload.
 * Returns an abort function.
 */
export async function streamChat(question: string, handlers: StreamHandlers): Promise<() => void> {
  const controller = new AbortController();
  (async () => {
    let res: Response;
    try {
      res = await fetch("/rag/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });
    } catch (e) {
      if (!controller.signal.aborted) {
        handlers.onError(e instanceof Error ? e.message : "Connection failed");
      }
      return;
    }
    if (!res.ok || !res.body) {
      handlers.onError(`Request failed with ${res.status}`);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let remainder = "";
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const { events, remainder: next } = parseSseChunk(decoder.decode(value, { stream: true }), remainder);
        remainder = next;
        for (const { event, data } of events) {
          if (event === "text") handlers.onDelta(data);
          else if (event === "result") {
            try {
              handlers.onResult(JSON.parse(data) as ChatResult);
            } catch {
              handlers.onError("Could not parse the final result payload");
            }
          }
        }
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        handlers.onError(e instanceof Error ? e.message : "Stream interrupted");
      }
    }
  })();
  return () => controller.abort();
}
