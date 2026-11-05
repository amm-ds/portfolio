/**
 * HTTP client for the agent-chat backend: POST /chat (SSE) plus conversation
 * CRUD. `ChatApi` is the surface the UI and the mock both implement.
 *
 * Older browsers without ReadableStream support would need an XHR fallback
 * (progress events give the same incremental stream); not implemented —
 * shortcut: targets modern Chromium/Firefox/WebKit, upgrade when a concrete
 * legacy target appears.
 */
import { ChatEventError, decodeSSEBlock, parseChatEvent } from "./events";
import type { ApprovalResponse, ChatEvent } from "./events";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  conversation_id?: string;
  messages: ChatMessage[];
  /** Operator decision for a pending approval; resumes the same run. */
  approval_response?: ApprovalResponse;
}

export interface ConversationMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation extends ConversationMeta {
  messages: ChatMessage[];
}

export interface HealthInfo {
  status: string;
  model?: string;
  provider?: string;
}

export interface ChatApi {
  health(): Promise<HealthInfo>;
  /** Stream one agent run as an async iterable of parsed events. */
  streamChat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<ChatEvent>;
  listConversations(): Promise<ConversationMeta[]>;
  createConversation(title?: string): Promise<ConversationMeta>;
  getConversation(id: string): Promise<Conversation>;
  renameConversation(id: string, title: string): Promise<ConversationMeta>;
  deleteConversation(id: string): Promise<void>;
}

async function* iterateSSE(body: ReadableStream<Uint8Array>, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep = buffer.indexOf("\n\n");
      while (sep !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const payload = decodeSSEBlock(block);
        if (payload !== null) {
          const event = parseChatEvent(payload);
          if (event !== null) yield event;
        }
        sep = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}

export class HttpChatApi implements ChatApi {
  constructor(private readonly baseUrl: string = "") {}

  async health(): Promise<HealthInfo> {
    const res = await fetch(`${this.baseUrl}/health`);
    if (!res.ok) throw new Error(`GET /health failed: ${res.status}`);
    return (await res.json()) as HealthInfo;
  }

  async *streamChat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<ChatEvent> {
    const res = await fetch(`${this.baseUrl}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify(req),
      signal,
    });
    if (!res.ok || !res.body) {
      throw new Error(`POST /chat failed: ${res.status}`);
    }
    try {
      for await (const event of iterateSSE(res.body, signal)) {
        yield event;
      }
    } catch (error) {
      if (error instanceof ChatEventError) throw error;
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
      throw error;
    }
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: { "content-type": "application/json" },
      ...init,
    });
    if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
    return (await res.json()) as T;
  }

  listConversations(): Promise<ConversationMeta[]> {
    return this.json("/conversations");
  }

  createConversation(title?: string): Promise<ConversationMeta> {
    return this.json("/conversations", { method: "POST", body: JSON.stringify({ title }) });
  }

  getConversation(id: string): Promise<Conversation> {
    return this.json(`/conversations/${encodeURIComponent(id)}`);
  }

  renameConversation(id: string, title: string): Promise<ConversationMeta> {
    return this.json(`/conversations/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  }

  async deleteConversation(id: string): Promise<void> {
    await this.json(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
  }
}
