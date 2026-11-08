import {
  parseAnalysisResponse,
  parseDocumentRecord,
  parsePageChatResponse,
  parseUploadResponse,
} from "./contracts";
import type {
  AnalysisResponse,
  DocumentRecord,
  PageChatMessage,
  PageChatResponse,
  UploadResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export const DEV_TENANT = import.meta.env.VITE_DEV_TENANT ?? "demo";
export const DEV_ACTOR = import.meta.env.VITE_DEV_ACTOR ?? "developer";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId: string | null = null,
    public readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | null;
}

function devHeaders(headers: Headers): void {
  if (import.meta.env.DEV) {
    headers.set("X-Dev-Tenant", DEV_TENANT);
    headers.set("X-Dev-Actor", DEV_ACTOR);
  }
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  let body: { error?: { code?: string; message?: string; request_id?: string | null } } | null = null;
  try {
    body = await response.json();
  } catch {
    // Stable fallback for proxy/server responses outside the API envelope.
  }
  return new ApiError(
    response.status,
    body?.error?.code ?? `http_${response.status}`,
    body?.error?.message ?? `Request failed with HTTP ${response.status}.`,
    body?.error?.request_id ?? response.headers.get("x-request-id"),
  );
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  devHeaders(headers);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Cannot reach the document-intelligence API.");
  }

  if (!response.ok) throw await parseErrorBody(response);
  return (await response.json()) as T;
}

async function requestBytes(path: string, signal?: AbortSignal): Promise<Response> {
  const headers = new Headers();
  devHeaders(headers);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers, signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Cannot reach the document-intelligence API.");
  }
  if (!response.ok) throw await parseErrorBody(response);
  return response;
}

function jsonRequest(body: unknown): Pick<RequestOptions, "headers" | "body"> {
  return {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export type ExportFormat = "json" | "md";

export const api = {
  async documents(signal?: AbortSignal): Promise<DocumentRecord[]> {
    const response = await request<unknown[]>("/documents", { signal });
    if (!Array.isArray(response)) throw new Error("Invalid document list: expected an array.");
    return response.map(parseDocumentRecord);
  },

  async upload(file: File, signal?: AbortSignal): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file, file.name);
    const response = await request<unknown>("/documents", { method: "POST", body: form, signal });
    return parseUploadResponse(response);
  },

  async analysis(documentId: string, signal?: AbortSignal): Promise<AnalysisResponse> {
    const response = await request<unknown>(`/documents/${documentId}/analysis`, { signal });
    return parseAnalysisResponse(response);
  },

  async reanalyze(documentId: string, signal?: AbortSignal): Promise<void> {
    await request<unknown>(`/documents/${documentId}/reanalyze`, { method: "POST", signal });
  },

  async pageChat(
    documentId: string,
    page: number,
    messages: PageChatMessage[],
    signal?: AbortSignal,
  ): Promise<PageChatResponse> {
    const response = await request<unknown>(`/documents/${documentId}/pages/${page}/chat`, {
      method: "POST",
      ...jsonRequest({ messages }),
      signal,
    });
    return parsePageChatResponse(response);
  },

  async exportAnalysis(documentId: string, format: ExportFormat): Promise<Blob> {
    const response = await requestBytes(`/documents/${documentId}/analysis/export?format=${format}`);
    return response.blob();
  },

  async exportPage(documentId: string, page: number, format: ExportFormat): Promise<Blob> {
    const response = await requestBytes(`/documents/${documentId}/pages/${page}/export?format=${format}`);
    return response.blob();
  },

  async content(documentId: string, signal?: AbortSignal): Promise<ArrayBuffer> {
    const response = await requestBytes(`/documents/${documentId}/content`, signal);
    return response.arrayBuffer();
  },
};
