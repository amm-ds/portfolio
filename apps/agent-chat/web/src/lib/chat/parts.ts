/**
 * Message-parts reducer: raw chat events → renderable parts for one assistant
 * turn. Pure and fold-based so the UI can re-reduce from scratch at any point.
 */
import type { ChatEvent, ToolCall } from "./events";

/** An approval as the UI needs it: request + the decision once made. */
export interface ApprovalState {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  reason?: string;
  status: "pending" | "approved" | "rejected";
  note?: string;
}

export type Part =
  | { kind: "text"; text: string }
  | { kind: "tool_call"; call: ToolCall }
  | { kind: "approval"; approval: ApprovalState };

export type StepKind = "plan" | "tool" | "critique" | "answer";

export interface Step {
  kind: StepKind;
  /** Tool name for kind "tool", otherwise a short text preview. */
  label: string;
  status: "done" | "running" | "error" | "pending";
}

/**
 * Fold a stream of events into parts. Consecutive text deltas merge into one
 * text part; tool_call updates merge by id; the approval decision merges into
 * the matching approval part.
 */
export function reduceEvents(events: readonly ChatEvent[]): Part[] {
  const parts: Part[] = [];
  for (const event of events) {
    switch (event.type) {
      case "text_delta": {
        const last = parts[parts.length - 1];
        if (last?.kind === "text") {
          parts[parts.length - 1] = { kind: "text", text: last.text + event.delta };
        } else {
          parts.push({ kind: "text", text: event.delta });
        }
        break;
      }
      case "tool_call": {
        const index = parts.findIndex((p) => p.kind === "tool_call" && p.call.id === event.tool_call.id);
        if (index === -1) {
          parts.push({ kind: "tool_call", call: event.tool_call });
        } else {
          const part = parts[index];
          if (part.kind === "tool_call") {
            parts[index] = { kind: "tool_call", call: { ...part.call, ...event.tool_call } };
          }
        }
        break;
      }
      case "approval_request": {
        const index = parts.findIndex((p) => p.kind === "approval" && p.approval.id === event.approval.id);
        if (index === -1) {
          parts.push({
            kind: "approval",
            approval: { ...event.approval, status: "pending" },
          });
        }
        break;
      }
      case "approval_response": {
        const index = parts.findIndex((p) => p.kind === "approval" && p.approval.id === event.approval.id);
        if (index !== -1) {
          const part = parts[index];
          if (part.kind === "approval") {
            parts[index] = {
              kind: "approval",
              approval: {
                ...part.approval,
                status: event.approval.approved ? "approved" : "rejected",
                note: event.approval.note,
              },
            };
          }
        }
        break;
      }
      case "usage":
      case "done":
        break;
    }
  }
  return parts;
}

function preview(text: string, max = 48): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length <= max ? flat : `${flat.slice(0, max - 1)}…`;
}

/**
 * Derive the run's step timeline from parts:
 *   first text block (before any tool call)      → plan
 *   each tool_call                                → tool
 *   text between tool calls                       → critique
 *   trailing text block after the last tool call  → answer
 */
export function deriveSteps(parts: readonly Part[]): Step[] {
  const steps: Step[] = [];
  let seenTool = false;
  for (const part of parts) {
    if (part.kind === "tool_call") {
      steps.push({
        kind: "tool",
        label: part.call.name,
        status: part.call.status === "running" ? "running" : part.call.status,
      });
      seenTool = true;
    } else if (part.kind === "approval") {
      steps.push({
        kind: "tool",
        label: part.approval.tool,
        status: part.approval.status === "pending" ? "pending" : "done",
      });
      seenTool = true;
    } else if (part.text.trim() !== "") {
      steps.push({
        kind: seenTool ? "critique" : "plan",
        label: preview(part.text),
        status: "done",
      });
    }
  }
  if (steps.length > 0) {
    const lastText = [...parts].reverse().find((p) => p.kind === "text" && p.text.trim() !== "");
    const hasTool = parts.some((p) => p.kind === "tool_call");
    if (hasTool && lastText) {
      const lastStep = steps[steps.length - 1];
      if (lastStep.kind === "critique") lastStep.kind = "answer";
    }
  }
  return steps;
}
