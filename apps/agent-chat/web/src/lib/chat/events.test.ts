import { describe, expect, it } from "vitest";
import { ChatEventError, decodeSSEBlock, parseChatEvent } from "./events";

describe("parseChatEvent", () => {
  it("parses text_delta", () => {
    expect(parseChatEvent('{"type":"text_delta","delta":"hi"}')).toEqual({
      type: "text_delta",
      delta: "hi",
    });
  });

  it("parses a running tool_call and its terminal update", () => {
    const running = parseChatEvent(
      '{"type":"tool_call","tool_call":{"id":"tc_1","name":"search_docs","args":{"q":"uptime"},"status":"running"}}',
    );
    expect(running).toEqual({
      type: "tool_call",
      tool_call: { id: "tc_1", name: "search_docs", args: { q: "uptime" }, status: "running" },
    });
    const done = parseChatEvent(
      '{"type":"tool_call","tool_call":{"id":"tc_1","name":"search_docs","args":{"q":"uptime"},"status":"done","result":"3 hits"}}',
    );
    expect(done).toMatchObject({ type: "tool_call", tool_call: { id: "tc_1", status: "done", result: "3 hits" } });
  });

  it("parses approval_request / approval_response", () => {
    expect(
      parseChatEvent(
        '{"type":"approval_request","approval":{"id":"ap_1","tool":"send_email","args":{"to":"a@b.c"},"reason":"external side effect"}}',
      ),
    ).toEqual({
      type: "approval_request",
      approval: { id: "ap_1", tool: "send_email", args: { to: "a@b.c" }, reason: "external side effect" },
    });
    expect(
      parseChatEvent('{"type":"approval_response","approval":{"id":"ap_1","approved":false,"note":"no"}}'),
    ).toEqual({ type: "approval_response", approval: { id: "ap_1", approved: false, note: "no" } });
  });

  it("parses usage and done with citations and uncertainty", () => {
    expect(parseChatEvent('{"type":"usage","usage":{"tokens":1234,"cost":0.03}}')).toEqual({
      type: "usage",
      usage: { tokens: 1234, cost: 0.03 },
    });
    expect(
      parseChatEvent(
        '{"type":"done","done":{"answer":"final","citations":[{"source":"runbook.md","locator":"p. 2"}],"uncertainty":"single source"}}',
      ),
    ).toEqual({
      type: "done",
      done: {
        answer: "final",
        citations: [{ source: "runbook.md", locator: "p. 2" }],
        uncertainty: "single source",
      },
    });
  });

  it("returns null for unknown types", () => {
    expect(parseChatEvent('{"type":"ping"}')).toBeNull();
  });

  it("throws on malformed JSON and bad shapes", () => {
    expect(() => parseChatEvent("not json")).toThrow(ChatEventError);
    expect(() => parseChatEvent('{"type":"text_delta"}')).toThrow(/delta/);
    expect(() => parseChatEvent('{"type":"tool_call","tool_call":{"id":"x","name":"y","args":{},"status":"weird"}}')).toThrow(/status/);
    expect(() => parseChatEvent('{"type":"usage","usage":{"tokens":"many","cost":1}}')).toThrow(/tokens/);
    expect(() => parseChatEvent('{"type":"done","done":{"answer":"x","citations":[{"locator":"p1"}]}}')).toThrow(/source/);
    expect(() => parseChatEvent('{}')).toThrow(/type/);
  });
});

describe("decodeSSEBlock", () => {
  it("joins data lines and strips the leading space", () => {
    expect(decodeSSEBlock('data: {"type":"text_delta","delta":"a"}\ndata: {"type":"text_delta","delta":"b"}')).toBe(
      '{"type":"text_delta","delta":"a"}\n{"type":"text_delta","delta":"b"}',
    );
  });

  it("ignores comments and other fields", () => {
    expect(decodeSSEBlock(": keep-alive\nevent: text_delta\nid: 7\nretry: 100\ndata: x")).toBe("x");
  });

  it("returns null for comment-only or empty blocks", () => {
    expect(decodeSSEBlock(": ping")).toBeNull();
    expect(decodeSSEBlock("")).toBeNull();
  });
});
