import { describe, expect, it } from "vitest";
import type { ChatEvent } from "./events";
import { commitFinalAnswer, deriveSteps, reduceEvents } from "./parts";

const scripted: ChatEvent[] = [
  { type: "text_delta", delta: "I'll check the docs, " },
  { type: "text_delta", delta: "then the metrics." },
  { type: "tool_call_start", call_id: "tc_1", name: "search_docs", args: { q: "uptime" } },
  { type: "tool_call_end", call_id: "tc_1", name: "search_docs", result: "3 hits" },
  { type: "approval_request", approval_id: "ap_1", tool: "restart_service", summary: "production impact" },
  { type: "approval_response", approval_id: "ap_1", approved: true },
  { type: "text_delta", delta: "Approved — restarting." },
  {
    type: "done",
    answer: { text: "done", citations: [], uncertainty: "low" },
    usage: { input_tokens: 400, output_tokens: 112, requests: 3 },
    conversation_id: "conv_1",
  },
];

describe("reduceEvents", () => {
  it("merges consecutive deltas into one text part", () => {
    const parts = reduceEvents(scripted);
    expect(parts[0]).toEqual({ kind: "text", text: "I'll check the docs, then the metrics." });
  });

  it("opens a tool part on start and closes it on end, keeping the args", () => {
    const parts = reduceEvents(scripted);
    const tool = parts.find((p) => p.kind === "tool_call");
    expect(tool).toMatchObject({
      call: { id: "tc_1", name: "search_docs", args: { q: "uptime" }, status: "done", result: "3 hits" },
    });
  });

  it("folds the approval decision into the approval part", () => {
    const parts = reduceEvents(scripted);
    const approval = parts.find((p) => p.kind === "approval");
    expect(approval).toMatchObject({
      approval: { id: "ap_1", tool: "restart_service", summary: "production impact", status: "approved" },
    });
  });

  it("replaces all trailing answer fragments while preserving tools and earlier text", () => {
    const streamed = reduceEvents(scripted);
    const committed = commitFinalAnswer(
      [...streamed, { kind: "text", text: "ed, your preferred cloud is GCP." }],
      "Remembered, your preferred cloud is GCP.",
    );

    expect(committed[0]).toMatchObject({ kind: "text", text: "I'll check the docs, then the metrics." });
    expect(committed.some((part) => part.kind === "tool_call")).toBe(true);
    expect(committed[committed.length - 1]).toEqual({
      kind: "text",
      text: "Remembered, your preferred cloud is GCP.",
    });
    expect(committed).not.toContainEqual({ kind: "text", text: "ed, your preferred cloud is GCP." });
  });

  it("ignores done events", () => {
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
        { type: "tool_call_start", call_id: "t", name: "query", args: {} },
      ]),
    );
    expect(steps[1]).toMatchObject({ kind: "tool", status: "running" });
  });

  it("returns an empty timeline for no parts", () => {
    expect(deriveSteps([])).toEqual([]);
  });
});
