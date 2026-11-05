/**
 * Chat event contract shared with the agent-chat backend (the source of
 * truth: src/agent_chat/api/events.py).
 *
 * Wire format: Server-Sent Events, one JSON object per `data:` payload, e.g.
 *
 *     data: {"type":"text_delta","delta":"Let me "}
 *
 *     data: {"type":"tool_call_start","call_id":"fake_call_1","name":"search_docs","args":{"q":"uptime"}}
 *
 * The stream ends with the sentinel `data: [DONE]` (handled in client.ts).
 * A tool call opens with `tool_call_start` and closes with the matching
 * `tool_call_end` (same `call_id`). `approval_request` parks the run: the
 * client answers with POST /approvals/{approval_id} and the server then emits
 * `approval_response` on the same stream as the run resumes. `usage` rides on
 * the `done` event, and `error` carries `{code, message}`.
 *
 * Unknown event types decode to null (forward-compatible skip); a payload
 * that claims a known type but violates its shape throws ChatEventError.
 */

export interface ToolCallStart {
  type: "tool_call_start";
  call_id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolCallEnd {
  type: "tool_call_end";
  call_id: string;
  name: string;
  result: string;
}

export interface ApprovalRequest {
  type: "approval_request";
  approval_id: string;
  tool: string;
  /** Human-readable why this tool needs confirmation. */
  summary: string;
}

export interface ApprovalResponse {
  type: "approval_response";
  approval_id: string;
  approved: boolean;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  requests: number;
}

export interface Citation {
  source: string;
  /** The exact words the claim rests on. */
  quote: string;
}

export type Uncertainty = "low" | "medium" | "high";

export interface Answer {
  text: string;
  citations: Citation[];
  /** The model's own calibration. */
  uncertainty: Uncertainty;
}

export interface Done {
  type: "done";
  answer: Answer;
  usage: Usage;
  conversation_id: string;
}

export interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
}

export type ChatEvent =
  | { type: "text_delta"; delta: string }
  | ToolCallStart
  | ToolCallEnd
  | ApprovalRequest
  | ApprovalResponse
  | Done
  | ErrorEvent;

export class ChatEventError extends Error {
  constructor(
    message: string,
    readonly payload: string,
  ) {
    super(message);
    this.name = "ChatEventError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireString(obj: Record<string, unknown>, key: string, ctx: string): string {
  const value = obj[key];
  if (typeof value !== "string") {
    throw new ChatEventError(`${ctx}: expected string "${key}"`, JSON.stringify(obj));
  }
  return value;
}

function requireNumber(obj: Record<string, unknown>, key: string, ctx: string): number {
  const value = obj[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ChatEventError(`${ctx}: expected number "${key}"`, JSON.stringify(obj));
  }
  return value;
}

function requireArgs(obj: Record<string, unknown>, ctx: string): Record<string, unknown> {
  const value = obj.args;
  if (!isRecord(value)) {
    throw new ChatEventError(`${ctx}: expected object "args"`, JSON.stringify(obj));
  }
  return value;
}

function decodeUsage(value: unknown, ctx: string): Usage {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "usage"`, String(value));
  return {
    input_tokens: requireNumber(value, "input_tokens", ctx),
    output_tokens: requireNumber(value, "output_tokens", ctx),
    requests: requireNumber(value, "requests", ctx),
  };
}

function decodeAnswer(value: unknown, ctx: string): Answer {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "answer"`, String(value));
  const rawCitations = value.citations;
  const citations: Citation[] = [];
  if (!Array.isArray(rawCitations)) {
    throw new ChatEventError(`${ctx}: expected array "citations"`, JSON.stringify(value));
  }
  for (const [i, raw] of rawCitations.entries()) {
    if (!isRecord(raw) || typeof raw.source !== "string" || typeof raw.quote !== "string") {
      throw new ChatEventError(`${ctx}: citation ${i} needs string "source" and "quote"`, JSON.stringify(raw));
    }
    citations.push({ source: raw.source, quote: raw.quote });
  }
  const uncertainty = value.uncertainty;
  if (uncertainty !== "low" && uncertainty !== "medium" && uncertainty !== "high") {
    throw new ChatEventError(`${ctx}: bad uncertainty`, JSON.stringify(value));
  }
  return { text: requireString(value, "text", ctx), citations, uncertainty };
}

function decodeDone(raw: Record<string, unknown>, ctx: string): Done {
  return {
    type: "done",
    answer: decodeAnswer(raw.answer, ctx),
    usage: decodeUsage(raw.usage, ctx),
    conversation_id: requireString(raw, "conversation_id", ctx),
  };
}

/** Parse one SSE `data` payload. Returns null for unknown types (skipped). */
export function parseChatEvent(payload: string): ChatEvent | null {
  let raw: unknown;
  try {
    raw = JSON.parse(payload);
  } catch {
    throw new ChatEventError("invalid JSON", payload);
  }
  if (!isRecord(raw) || typeof raw.type !== "string") {
    throw new ChatEventError("event needs a string \"type\"", payload);
  }
  const ctx = `event ${raw.type}`;
  switch (raw.type) {
    case "text_delta":
      return { type: "text_delta", delta: requireString(raw, "delta", ctx) };
    case "tool_call_start":
      return {
        type: "tool_call_start",
        call_id: requireString(raw, "call_id", ctx),
        name: requireString(raw, "name", ctx),
        args: requireArgs(raw, ctx),
      };
    case "tool_call_end":
      return {
        type: "tool_call_end",
        call_id: requireString(raw, "call_id", ctx),
        name: requireString(raw, "name", ctx),
        result: requireString(raw, "result", ctx),
      };
    case "approval_request":
      return {
        type: "approval_request",
        approval_id: requireString(raw, "approval_id", ctx),
        tool: requireString(raw, "tool", ctx),
        summary: requireString(raw, "summary", ctx),
      };
    case "approval_response":
      if (typeof raw.approved !== "boolean") {
        throw new ChatEventError(`${ctx}: expected boolean "approved"`, JSON.stringify(raw));
      }
      return {
        type: "approval_response",
        approval_id: requireString(raw, "approval_id", ctx),
        approved: raw.approved,
      };
    case "done":
      return decodeDone(raw, ctx);
    case "error":
      return {
        type: "error",
        code: requireString(raw, "code", ctx),
        message: requireString(raw, "message", ctx),
      };
    default:
      return null;
  }
}

/**
 * Extract the joined `data` payload from one SSE block (the text between
 * blank lines). Comment lines (starting with ":") and event/id/retry fields
 * are ignored per the SSE spec. Returns null when the block carries no data.
 */
export function decodeSSEBlock(block: string): string | null {
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "data") data.push(value);
  }
  return data.length === 0 ? null : data.join("\n");
}
