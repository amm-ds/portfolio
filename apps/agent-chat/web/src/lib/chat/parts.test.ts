import { describe, expect, it } from "vitest";
import type { ChatEvent } from "./events";
import { deriveSteps, reduceEvents } from "./parts";

const scripted: ChatEvent[] = [
  { type: "text_delta", delta: "I'll check the docs, " },
  { type: "text_delta", delta: "then the metrics." },
  {
    type: "tool_call",
    tool_call: { id: "tc_1", name: "search_docs", args: { q: "uptime" }, status: "running" },
  },
  {
    type: "tool_call",
    tool_call: { id: "tc_1", name: "search_docs", args: { q: "uptime" }, status: "done", result: "3 hits" },
  },
  {
    type: "approval_request",
    approval: { id: "ap_1", tool: "restart_service", args: { service: "api" }, reason: "production impact" },
  },
  { type: "approval_response", approval: { id: "ap_1", approved: true } },
  { type: "text_delta", delta: "Approved — restarting." },
  { type: "usage", usage: { tokens: 512, cost: 0.01 } },
  {
    type: "done",
    done: { answer: "done", citations: [] },
  },
];

describe("reduceEvents", () => {
  it("merges consecutive deltas into one text part", () => {
    const parts = reduceEvents(scripted);
    expect(parts[0]).toEqual({ kind: "text", text: "I'll check the docs, then the metrics." });
  });

  it("merges tool_call updates by id, keeping the original args", () => {
    const parts = reduceEvents(scripted);
    const tool = parts.find((p) => p.kind === "tool_call");
    expect(tool).toMatchObject({
      call: { id: "tc_1", name: "search_docs", args: { q: "uptime" }, status: "done", result: "3 hits" },
    });
  });

  it("folds the approval decision into the approval part", () => {
    const parts = reduceEvents(scripted);
    const approval = parts.find((p) => p.kind === "approval");
    expect(approval).toMatchObject({ approval: { id: "ap_1", status: "approved" } });
  });

  it("ignores usage and done events", () => {
    expect(reduceEvents(scripted).filter((p) => p.kind === "text")).toHaveLength(2);
  });
});

describe("deriveSteps", () => {
  it("labels the timeline plan → tool → answer", () => {
    const steps = deriveSteps(reduceEvents(scripted));
    expect(steps.map((s) => s.kind)).toEqual(["plan", "tool", "tool", "answer"]);
    expect(steps.map((s) => s.label)).toEqual([
      "I'll check the docs, then the metrics.",
      "search_docs",
      "restart_service",
      "Approved — restarting.",
    ]);
  });

  it("marks a running tool call as running", () => {
    const steps = deriveSteps(
      reduceEvents([
        { type: "text_delta", delta: "plan" },
        { type: "tool_call", tool_call: { id: "t", name: "query", args: {}, status: "running" } },
      ]),
    );
    expect(steps[1]).toMatchObject({ kind: "tool", status: "running" });
  });

  it("returns an empty timeline for no parts", () => {
    expect(deriveSteps([])).toEqual([]);
  });
});
