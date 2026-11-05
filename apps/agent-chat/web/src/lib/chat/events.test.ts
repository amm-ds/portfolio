import { describe, expect, it } from "vitest";
import { ChatEventError, decodeSSEBlock, parseChatEvent } from "./events";

describe("parseChatEvent", () => {
  it("parses text_delta", () => {
    expect(parseChatEvent('{"type":"text_delta","delta":"hi"}')).toEqual({
      type: "text_delta",
      delta: "hi",
    });
  });

  it("parses the tool_call_start / tool_call_end pair", () => {
    const start = parseChatEvent(
      '{"type":"tool_call_start","call_id":"fake_call_1","name":"search_docs","args":{"q":"uptime"}}',
    );
    expect(start).toEqual({
      type: "tool_call_start",
      call_id: "fake_call_1",
      name: "search_docs",
      args: { q: "uptime" },
    });
    const end = parseChatEvent(
      '{"type":"tool_call_end","call_id":"fake_call_1","name":"search_docs","result":"3 hits"}',
    );
    expect(end).toEqual({
      type: "tool_call_end",
      call_id: "fake_call_1",
      name: "search_docs",
      result: "3 hits",
    });
  });

  it("parses approval_request / approval_response", () => {
    expect(
      parseChatEvent(
        '{"type":"approval_request","approval_id":"ap_1","tool":"send_message","summary":"posts to #ops"}',
      ),
    ).toEqual({
      type: "approval_request",
      approval_id: "ap_1",
      tool: "send_message",
      summary: "posts to #ops",
    });
    expect(
      parseChatEvent('{"type":"approval_response","approval_id":"ap_1","approved":false}'),
    ).toEqual({ type: "approval_response", approval_id: "ap_1", approved: false });
  });

  it("parses done with the typed answer, usage, and conversation id", () => {
    expect(
      parseChatEvent(
        '{"type":"done","answer":{"text":"final","citations":[{"source":"runbook.md","quote":"restart when error rate > 1%"}],"uncertainty":"low"},"usage":{"input_tokens":12,"output_tokens":6,"requests":2},"conversation_id":"conv_1"}',
      ),
    ).toEqual({
      type: "done",
      answer: {
        text: "final",
        citations: [{ source: "runbook.md", quote: "restart when error rate > 1%" }],
        uncertainty: "low",
      },
      usage: { input_tokens: 12, output_tokens: 6, requests: 2 },
      conversation_id: "conv_1",
    });
  });

  it("parses error with code and message", () => {
    expect(parseChatEvent('{"type":"error","code":"assertion_error","message":"boom"}')).toEqual({
      type: "error",
      code: "assertion_error",
      message: "boom",
    });
  });

  it("returns null for unknown types", () => {
    expect(parseChatEvent('{"type":"ping"}')).toBeNull();
  });

  it("throws on malformed JSON and bad shapes", () => {
    expect(() => parseChatEvent("not json")).toThrow(ChatEventError);
    expect(() => parseChatEvent('{"type":"text_delta"}')).toThrow(/delta/);
    expect(() =>
      parseChatEvent('{"type":"tool_call_start","call_id":"x","name":"y"}'),
    ).toThrow(/args/);
    expect(() =>
      parseChatEvent('{"type":"tool_call_end","call_id":"x","name":"y"}'),
    ).toThrow(/result/);
    expect(() =>
      parseChatEvent('{"type":"approval_request","approval_id":"a","tool":"t"}'),
    ).toThrow(/summary/);
    expect(() =>
      parseChatEvent('{"type":"approval_response","approval_id":"a","approved":"yes"}'),
    ).toThrow(/approved/);
    expect(() =>
      parseChatEvent(
        '{"type":"done","answer":{"text":"x","citations":[],"uncertainty":"low"},"usage":{"input_tokens":"many","output_tokens":1,"requests":1},"conversation_id":"c"}',
      ),
    ).toThrow(/input_tokens/);
    expect(() =>
      parseChatEvent(
        '{"type":"done","answer":{"text":"x","citations":[{"source":"s"}],"uncertainty":"low"},"usage":{"input_tokens":1,"output_tokens":1,"requests":1},"conversation_id":"c"}',
      ),
    ).toThrow(/quote/);
    expect(() =>
      parseChatEvent(
        '{"type":"done","answer":{"text":"x","citations":[],"uncertainty":"certain"},"usage":{"input_tokens":1,"output_tokens":1,"requests":1},"conversation_id":"c"}',
      ),
    ).toThrow(/uncertainty/);
    expect(() => parseChatEvent('{"type":"error","code":"c"}')).toThrow(/message/);
    expect(() => parseChatEvent("{}")).toThrow(/type/);
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
