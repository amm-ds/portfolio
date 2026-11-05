/**
 * Chat event contract shared with the agent-chat backend.
 *
 * Wire format: Server-Sent Events, one JSON object per `data:` payload, e.g.
 *
 *     data: {"type":"text_delta","delta":"Let me "}
 *
 *     data: {"type":"tool_call","tool_call":{"id":"tc_1","name":"search_docs","args":{"q":"uptime"},"status":"running"}}
 *
 * `tool_call` may arrive again with the same `id` and a later `status`
 * ("done"/"error") plus `result`; clients merge updates by id.
 * `approval_response` is sent client → server inside the /chat request body
 * (see client.ts) and echoed back on the wire so a single event fold drives
 * the UI.
 *
 * Unknown event types decode to null (forward-compatible skip); a payload
 * that claims a known type but violates its shape throws ChatEventError.
 */

export type ToolCallStatus = "running" | "done" | "error";

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: ToolCallStatus;
  /** Present when status is "done" (serialized result) or "error" (message). */
  result?: string;
}

export interface ApprovalRequest {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  /** Human-readable why this tool needs confirmation. */
  reason?: string;
}

export interface ApprovalResponse {
  id: string;
  approved: boolean;
  /** Optional operator note recorded with the decision. */
  note?: string;
}

export interface Usage {
  tokens: number;
  cost: number;
}

export interface Citation {
  source: string;
  /** Optional locator inside the source (page, section, row). */
  locator?: string;
  snippet?: string;
}

export interface Done {
  answer: string;
  citations: Citation[];
  /** Set when the agent flags low confidence or missing evidence. */
  uncertainty?: string;
}

export type ChatEvent =
  | { type: "text_delta"; delta: string }
  | { type: "tool_call"; tool_call: ToolCall }
  | { type: "approval_request"; approval: ApprovalRequest }
  | { type: "approval_response"; approval: ApprovalResponse }
  | { type: "usage"; usage: Usage }
  | { type: "done"; done: Done };

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

function optionalString(obj: Record<string, unknown>, key: string): string | undefined {
  const value = obj[key];
  return typeof value === "string" ? value : undefined;
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

function decodeToolCall(value: unknown, ctx: string): ToolCall {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "tool_call"`, String(value));
  const status = requireString(value, "status", ctx);
  if (status !== "running" && status !== "done" && status !== "error") {
    throw new ChatEventError(`${ctx}: bad tool_call status "${status}"`, JSON.stringify(value));
  }
  const call: ToolCall = {
    id: requireString(value, "id", ctx),
    name: requireString(value, "name", ctx),
    args: requireArgs(value, ctx),
    status,
  };
  const result = optionalString(value, "result");
  if (result !== undefined) call.result = result;
  return call;
}

function decodeApprovalRequest(value: unknown, ctx: string): ApprovalRequest {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "approval"`, String(value));
  const approval: ApprovalRequest = {
    id: requireString(value, "id", ctx),
    tool: requireString(value, "tool", ctx),
    args: requireArgs(value, ctx),
  };
  const reason = optionalString(value, "reason");
  if (reason !== undefined) approval.reason = reason;
  return approval;
}

function decodeApprovalResponse(value: unknown, ctx: string): ApprovalResponse {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "approval"`, String(value));
  if (typeof value.approved !== "boolean") {
    throw new ChatEventError(`${ctx}: expected boolean "approved"`, JSON.stringify(value));
  }
  const response: ApprovalResponse = {
    id: requireString(value, "id", ctx),
    approved: value.approved,
  };
  const note = optionalString(value, "note");
  if (note !== undefined) response.note = note;
  return response;
}

function decodeUsage(value: unknown, ctx: string): Usage {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "usage"`, String(value));
  return {
    tokens: requireNumber(value, "tokens", ctx),
    cost: requireNumber(value, "cost", ctx),
  };
}

function decodeDone(value: unknown, ctx: string): Done {
  if (!isRecord(value)) throw new ChatEventError(`${ctx}: expected object "done"`, String(value));
  const rawCitations = value.citations;
  const citations: Citation[] = Array.isArray(rawCitations) ? [] : [];
  if (Array.isArray(rawCitations)) {
    for (const [i, raw] of rawCitations.entries()) {
      if (!isRecord(raw) || typeof raw.source !== "string") {
        throw new ChatEventError(`${ctx}: citation ${i} needs a string "source"`, JSON.stringify(raw));
      }
      const citation: Citation = { source: raw.source };
      if (typeof raw.locator === "string") citation.locator = raw.locator;
      if (typeof raw.snippet === "string") citation.snippet = raw.snippet;
      citations.push(citation);
    }
  }
  const done: Done = { answer: requireString(value, "answer", ctx), citations };
  const uncertainty = optionalString(value, "uncertainty");
  if (uncertainty !== undefined) done.uncertainty = uncertainty;
  return done;
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
    case "tool_call":
      return { type: "tool_call", tool_call: decodeToolCall(raw.tool_call, ctx) };
    case "approval_request":
      return { type: "approval_request", approval: decodeApprovalRequest(raw.approval, ctx) };
    case "approval_response":
      return { type: "approval_response", approval: decodeApprovalResponse(raw.approval, ctx) };
    case "usage":
      return { type: "usage", usage: decodeUsage(raw.usage, ctx) };
    case "done":
      return { type: "done", done: decodeDone(raw.done, ctx) };
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
