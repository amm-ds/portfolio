/**
 * HTTP client for the agent-chat backend (the wire contract lives in
 * src/agent_chat/api — this module mirrors it):
 *
 * - `POST /chat` — body `{"message", "conversation_id"?}`; one SSE stream of
 *   typed events (see events.ts) ending with `data: [DONE]`. While the stream
 *   is parked on an `approval_request`, the client answers with
 *   `POST /approvals/{approval_id}`; the same stream then emits
 *   `approval_response` and the rest of the run.
 * - `GET /conversations` returns `{"conversations": [...]}`; conversation ids
 *   arrive as `conversation_id` and are mapped to `id` here. There is no
 *   create/rename endpoint — a conversation is born from the first run and
 *   its id comes back in the `done` event.
 * - `GET /conversations/{id}` returns the pydantic-ai conversation dump; the
 *   message history is flattened to {role, content} pairs for the UI.
 * - Mutations require `X-API-Key` when the backend has one configured; pass
 *   it via `VITE_API_KEY`. Errors are the backend's envelope
 *   `{"error": {"code", "message", "request_id"}}`.
 *
 * Older browsers without ReadableStream support would need an XHR fallback
 * (progress events give the same incremental stream); not implemented —
 * shortcut: targets modern Chromium/Firefox/WebKit, upgrade when a concrete
 * legacy target appears.
 */
import { ChatEventError, decodeSSEBlock, parseChatEvent } from "./events";
import type { ChatEvent } from "./events";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ConversationMeta {
  id: string;
  title: string;
  updatedAt: string;
  messageCount?: number;
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
  /**
   * Answer a pending approval_request. The run's SSE stream stays open while
   * this is called; the server emits approval_response on that same stream.
   */
  decideApproval(approvalId: string, approved: boolean, signal?: AbortSignal): Promise<void>;
  listConversations(): Promise<ConversationMeta[]>;
  getConversation(id: string): Promise<Conversation>;
  deleteConversation(id: string): Promise<void>;
}

/** The backend's error envelope, stamped on every failed response. */
interface ErrorEnvelope {
  error?: { code?: string; message?: string; request_id?: string | null };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function raiseForStatus(res: Response, what: string): Promise<never> {
  let detail = res.statusText;
  let requestId = res.headers.get("x-request-id") ?? undefined;
  const text = await res.text().catch(() => "");
  try {
    const envelope = JSON.parse(text) as ErrorEnvelope;
    if (isRecord(envelope.error)) {
      detail = envelope.error.message ?? detail;
      requestId = envelope.error.request_id ?? requestId;
    }
  } catch {
    if (text) detail = text;
  }
  const suffix = requestId ? ` (request ${requestId})` : "";
  throw new Error(`${what} failed: ${res.status} ${detail}${suffix}`);
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
        if (payload === "[DONE]") return;
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

/** Flatten the pydantic-ai conversation dump (`{"messages": [...]}`) to
 * {role, content} pairs: user-prompt parts become user turns, text parts
 * assistant turns. The agent's structured `Answer` comes back as a
 * `final_result` tool call (pydantic-ai output_type), so its args' text is
 * the assistant turn in history; other tool calls/returns stay collapsed. */
function flattenMessages(conversation: unknown): ChatMessage[] {
  if (!isRecord(conversation) || !Array.isArray(conversation.messages)) return [];
  const messages: ChatMessage[] = [];
  for (const raw of conversation.messages) {
    if (!isRecord(raw) || !Array.isArray(raw.parts)) continue;
    const role = raw.kind === "request" ? "user" : raw.kind === "response" ? "assistant" : null;
    if (role === null) continue;
    const texts: string[] = [];
    for (const part of raw.parts) {
      if (!isRecord(part)) continue;
      if (
        (part.part_kind === "user-prompt" || part.part_kind === "text") &&
        typeof part.content === "string"
      ) {
        texts.push(part.content);
      } else if (
        part.part_kind === "tool-call" &&
        part.tool_name === "final_result" &&
        isRecord(part.args) &&
        typeof part.args.text === "string"
      ) {
        texts.push(part.args.text);
      }
    }
    const content = texts.join("\n\n");
    if (content !== "") messages.push({ role, content });
  }
  return messages;
}

export interface HttpChatApiOptions {
  /** Sent as X-API-Key when set (matches AGENT_CHAT_API_KEY on the server). */
  apiKey?: string;
}

export class HttpChatApi implements ChatApi {
  private readonly apiKey?: string;

  constructor(
    private readonly baseUrl: string = "",
    options: HttpChatApiOptions = {},
  ) {
    this.apiKey = options.apiKey || undefined;
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    return { ...extra, ...(this.apiKey ? { "x-api-key": this.apiKey } : {}) };
  }

  async health(): Promise<HealthInfo> {
    const res = await fetch(`${this.baseUrl}/health`, { headers: this.headers() });
    if (!res.ok) throw new Error(`GET /health failed: ${res.status}`);
    return (await res.json()) as HealthInfo;
  }

  async *streamChat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<ChatEvent> {
    const res = await fetch(`${this.baseUrl}/chat`, {
      method: "POST",
      headers: this.headers({ "content-type": "application/json", accept: "text/event-stream" }),
      body: JSON.stringify({ message: req.message, ...(req.conversation_id ? { conversation_id: req.conversation_id } : {}) }),
      signal,
    });
    if (!res.ok) await raiseForStatus(res, "POST /chat");
    if (!res.body) throw new Error("POST /chat failed: missing response body");
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

  async decideApproval(approvalId: string, approved: boolean, signal?: AbortSignal): Promise<void> {
    const res = await fetch(`${this.baseUrl}/approvals/${encodeURIComponent(approvalId)}`, {
      method: "POST",
      headers: this.headers({ "content-type": "application/json" }),
      body: JSON.stringify({ approved }),
      signal,
    });
    if (!res.ok) await raiseForStatus(res, `POST /approvals/${approvalId}`);
  }

  async listConversations(): Promise<ConversationMeta[]> {
    const res = await fetch(`${this.baseUrl}/conversations`, { headers: this.headers() });
    if (!res.ok) await raiseForStatus(res, "GET /conversations");
    const body = (await res.json()) as { conversations?: unknown };
    if (!isRecord(body) || !Array.isArray(body.conversations)) {
      throw new Error("GET /conversations: missing \"conversations\" array");
    }
    return body.conversations.map((raw, i) => {
      if (!isRecord(raw) || typeof raw.conversation_id !== "string" || typeof raw.title !== "string") {
        throw new Error(`GET /conversations: bad entry ${i}`);
      }
      const meta: ConversationMeta = {
        id: raw.conversation_id,
        title: raw.title,
        updatedAt: typeof raw.updated_at === "string" ? raw.updated_at : "",
      };
      if (typeof raw.message_count === "number") meta.messageCount = raw.message_count;
      return meta;
    });
  }

  async getConversation(id: string): Promise<Conversation> {
    const res = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      headers: this.headers(),
    });
    if (!res.ok) await raiseForStatus(res, `GET /conversations/${id}`);
    const body = (await res.json()) as { meta?: unknown; conversation?: unknown };
    if (!isRecord(body.meta) || typeof body.meta.conversation_id !== "string") {
      throw new Error(`GET /conversations/${id}: missing meta`);
    }
    return {
      id: body.meta.conversation_id,
      title: typeof body.meta.title === "string" ? body.meta.title : "",
      updatedAt: typeof body.meta.updated_at === "string" ? body.meta.updated_at : "",
      ...(typeof body.meta.message_count === "number" ? { messageCount: body.meta.message_count } : {}),
      messages: flattenMessages(body.conversation),
    };
  }

  async deleteConversation(id: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: this.headers(),
    });
    if (!res.ok) await raiseForStatus(res, `DELETE /conversations/${id}`);
  }
}
