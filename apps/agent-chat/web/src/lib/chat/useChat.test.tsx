import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChatApi, ChatRequest, Conversation, ConversationMeta, HealthInfo } from "./client";
import type { ChatEvent } from "./events";
import { useChat } from "./useChat";

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function conversation(id: string, text: string): Conversation {
  return {
    id,
    title: id,
    updatedAt: "2026-01-01T00:00:00Z",
    messages: [{ role: "assistant", content: text }],
  };
}

function done(id: string, text: string): ChatEvent {
  return {
    type: "done",
    answer: { text, citations: [], uncertainty: "low" },
    usage: { input_tokens: 12, output_tokens: 6, requests: 1 },
    conversation_id: id,
  };
}

class RaceChatApi implements ChatApi {
  readonly streamGate = deferred<void>();
  readonly streamStarted = deferred<void>();
  readonly deleteGate = deferred<void>();
  readonly histories = new Map<string, Deferred<Conversation>>();
  readonly requests: ChatRequest[] = [];

  constructor(
    private readonly metas: ConversationMeta[] = [],
    private readonly immediateHistory = false,
  ) {}

  async health(): Promise<HealthInfo> {
    return { status: "ok" };
  }

  async *streamChat(req: ChatRequest, _signal?: AbortSignal): AsyncIterable<ChatEvent> {
    this.requests.push(req);
    yield { type: "text_delta", delta: "stale draft" };
    this.streamStarted.resolve();
    // Deliberately ignore abort: the hook, not transport timing, must guard late events.
    await this.streamGate.promise;
    yield done(req.conversation_id ?? "old", "stale answer");
  }

  async decideApproval(): Promise<void> {}

  async listConversations(): Promise<ConversationMeta[]> {
    return this.metas;
  }

  async getConversation(id: string): Promise<Conversation> {
    if (this.immediateHistory) return conversation(id, `${id} history`);
    const pending = deferred<Conversation>();
    this.histories.set(id, pending);
    return pending.promise;
  }

  async deleteConversation(): Promise<void> {
    await this.deleteGate.promise;
  }
}

class ApprovalChatApi extends RaceChatApi {
  readonly decisionGate = deferred<void>();
  readonly serverDecision = deferred<void>();
  decisionCalls = 0;
  failNextDecision = false;

  override async *streamChat(): AsyncIterable<ChatEvent> {
    yield {
      type: "tool_call_start",
      call_id: "tool-1",
      name: "send_message",
      args: { channel: "ops", text: "full text" },
    };
    yield {
      type: "approval_request",
      approval_id: "approval-1",
      tool: "send_message",
      summary: "post to #ops",
      payload: { channel: "ops", text: "full text" },
    };
    this.streamStarted.resolve();
    await this.serverDecision.promise;
    yield { type: "approval_response", approval_id: "approval-1", approved: true };
    yield {
      type: "tool_call_end",
      call_id: "tool-1",
      name: "send_message",
      result: "Message sent to #ops.",
    };
    yield done("approval-conversation", "sent");
  }

  override async decideApproval(): Promise<void> {
    this.decisionCalls += 1;
    if (this.failNextDecision) {
      this.failNextDecision = false;
      throw new Error("decision transport failed");
    }
    await this.decisionGate.promise;
    this.serverDecision.resolve();
  }
}

describe("useChat stale work guards", () => {
  it("ignores a done event that arrives after creating a new conversation", async () => {
    const api = new RaceChatApi();
    const { result } = renderHook(() => useChat(api));
    await act(async () => {
      await result.current.send("old question");
      await api.streamStarted.promise;
    });
    expect(result.current.state.parts[0]).toEqual({ kind: "text", text: "stale draft" });

    act(() => result.current.create());
    await act(async () => {
      api.streamGate.resolve();
      await api.streamGate.promise;
    });

    await waitFor(() => expect(result.current.state.phase).toBe("idle"));
    expect(result.current.state.activeId).toBeNull();
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.usage).toBeNull();
  });

  it("keeps the latest selection when an older history load resolves last", async () => {
    const metas = [
      { id: "first", title: "first", updatedAt: "2026-01-02" },
      { id: "second", title: "second", updatedAt: "2026-01-01" },
    ];
    const api = new RaceChatApi(metas);
    const { result } = renderHook(() => useChat(api));
    await waitFor(() => expect(api.histories.has("first")).toBe(true));

    let selection!: Promise<void>;
    act(() => {
      selection = result.current.select("second");
    });
    await waitFor(() => expect(api.histories.has("second")).toBe(true));
    await act(async () => {
      api.histories.get("second")?.resolve(conversation("second", "second history"));
      await selection;
    });
    expect(result.current.state.messages[0].content).toBe("second history");

    await act(async () => {
      api.histories.get("first")?.resolve(conversation("first", "first history"));
      await api.histories.get("first")?.promise;
    });
    expect(result.current.state.activeId).toBe("second");
    expect(result.current.state.messages[0].content).toBe("second history");
  });

  it("does not let a pending history load overwrite a newly started run", async () => {
    const api = new RaceChatApi([{ id: "second", title: "second", updatedAt: "2026-01-01" }]);
    const { result } = renderHook(() => useChat(api));
    await waitFor(() => expect(api.histories.has("second")).toBe(true));

    let selection!: Promise<void>;
    act(() => {
      selection = result.current.select("second");
    });
    await act(async () => {
      await result.current.send("new question");
      await api.streamStarted.promise;
    });
    expect(api.requests[0]).toEqual({ message: "new question", conversation_id: "second" });
    expect(result.current.state.messages).toEqual([{ role: "user", content: "new question" }]);

    await act(async () => {
      api.histories.get("second")?.resolve(conversation("second", "late history"));
      await selection;
    });
    expect(result.current.state.messages).toEqual([{ role: "user", content: "new question" }]);
    await act(async () => {
      api.streamGate.resolve();
      await api.streamGate.promise;
    });
  });

  it("invalidates an active run before delete completes", async () => {
    const metas = [{ id: "old", title: "old", updatedAt: "2026-01-01" }];
    const api = new RaceChatApi(metas, true);
    const { result } = renderHook(() => useChat(api));
    await waitFor(() => expect(result.current.state.activeId).toBe("old"));
    await act(async () => {
      await result.current.send("still running");
      await api.streamStarted.promise;
    });

    let removal!: Promise<void>;
    act(() => {
      removal = result.current.remove("old");
    });
    expect(result.current.state.activeId).toBeNull();
    expect(result.current.state.messages).toEqual([]);

    await act(async () => {
      api.streamGate.resolve();
      await api.streamGate.promise;
    });
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.usage).toBeNull();

    await act(async () => {
      api.deleteGate.resolve();
      await removal;
    });
    expect(result.current.state.conversations).toEqual([]);
  });
});

describe("useChat approval decisions", () => {
  it("supports retry, blocks double submission, and waits for tool completion", async () => {
    const api = new ApprovalChatApi();
    const { result } = renderHook(() => useChat(api));
    await act(async () => {
      await result.current.send("notify ops");
      await api.streamStarted.promise;
    });

    api.failNextDecision = true;
    await act(async () => {
      result.current.respondApproval("approval-1", true);
      await Promise.resolve();
    });
    expect(result.current.state.parts.find((part) => part.kind === "approval")).toMatchObject({
      approval: { status: "failed", execution: "pending" },
    });

    act(() => result.current.respondApproval("approval-1", true));
    expect(result.current.state.parts.find((part) => part.kind === "approval")).toMatchObject({
      approval: { status: "submitting", execution: "pending" },
    });
    act(() => result.current.respondApproval("approval-1", false));
    expect(api.decisionCalls).toBe(2);

    await act(async () => {
      api.decisionGate.resolve();
      await api.serverDecision.promise;
    });
    await waitFor(() => expect(result.current.state.phase).toBe("idle"));
    const message = result.current.state.messages.at(-1);
    expect(message?.parts?.find((part) => part.kind === "approval")).toMatchObject({
      approval: { status: "approved", execution: "completed" },
    });
    expect(api.decisionCalls).toBe(2);
  });
});
