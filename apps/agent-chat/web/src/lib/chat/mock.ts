/**
 * Scripted mock transport for dev mode (VITE_MOCK=1): same ChatApi surface as
 * the HTTP client, backed by in-memory conversations and a canned agent run
 * (plan → search → metrics → approval-gated restart → answer). The approval
 * gate blocks the stream until the client re-posts with the matching
 * approval_response, mirroring the real backend's resume-on-approve contract.
 */
import type { ApprovalResponse, ChatEvent } from "./events";
import type { ChatApi, ChatMessage, ChatRequest, Conversation, ConversationMeta, HealthInfo } from "./client";

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export class MockChatApi implements ChatApi {
  private conversations = new Map<string, Conversation>();
  /** Runs parked mid-flight, keyed by approval id, resumed by the approval leg. */
  private pendingRuns = new Map<string, { conversationId: string; messages: ChatMessage[]; question: string }>();
  private seq = 0;

  constructor() {
    this.seed();
  }

  private seed(): void {
    const now = new Date(0).toISOString();
    this.conversations.set("mock-welcome", {
      id: "mock-welcome",
      title: "example: incident triage",
      created_at: now,
      updated_at: now,
      messages: [
        { role: "user", content: "why did p99 latency spike at 14:20?" },
        {
          role: "assistant",
          content:
            "I checked the deploy log and the metrics. The spike lines up with the `api` restart: p99 returned to baseline about 90s later. Nothing else anomalous in the window.",
        },
      ],
    });
  }

  async health(): Promise<HealthInfo> {
    return { status: "ok", model: "mock-agent-1", provider: "mock" };
  }

  async *streamChat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<ChatEvent> {
    const question = [...req.messages].reverse().find((m) => m.role === "user")?.content ?? "";

    // Approval leg: resume the run parked by the head leg with the operator's
    // decision, then persist the completed turn.
    if (req.approval_response) {
      const pending = this.pendingRuns.get(req.approval_response.id);
      this.pendingRuns.delete(req.approval_response.id);
      if (!pending) return;
      const answer = yield* this.runTail(req.approval_response, pending.question, signal);
      const conv = this.conversations.get(pending.conversationId);
      if (conv) {
        conv.messages = [...pending.messages, { role: "assistant", content: answer }];
        conv.updated_at = new Date().toISOString();
      }
      return;
    }

    const conversationId = req.conversation_id ?? this.ensureConversation(question);
    yield* this.runHead(question, signal);
    // The stream ends after approval_request; the run resumes on the leg above.
    this.pendingRuns.set("ap_restart", { conversationId, messages: req.messages, question });
  }

  private ensureConversation(title: string): string {
    const id = `mock-${++this.seq}`;
    const now = new Date().toISOString();
    this.conversations.set(id, { id, title: title.slice(0, 40) || "new conversation", created_at: now, updated_at: now, messages: [] });
    return id;
  }

  /** Head of the canned run: plan → search → metrics → approval_request. */
  private async *runHead(question: string, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
    const q = question.trim() || "status";
    const plan = "Plan: search the runbook for the reported symptom, pull the service metrics, then act on what I find. ";
    for (const word of plan.split(" ")) {
      await sleep(10, signal);
      yield { type: "text_delta", delta: `${word} ` };
    }

    await sleep(150, signal);
    yield {
      type: "tool_call",
      tool_call: { id: "tc_search", name: "search_docs", args: { q: q.slice(0, 60) }, status: "running" },
    };
    await sleep(300, signal);
    yield {
      type: "tool_call",
      tool_call: {
        id: "tc_search",
        name: "search_docs",
        args: { q: q.slice(0, 60) },
        status: "done",
        result: JSON.stringify({ hits: 2, top: ["runbook/incident-triage.md", "runbook/deploys.md"] }),
      },
    };

    for (const word of "The runbook points at the api service. Pulling live metrics before touching anything. ".split(" ")) {
      await sleep(10, signal);
      yield { type: "text_delta", delta: `${word} ` };
    }
    await sleep(200, signal);
    yield { type: "tool_call", tool_call: { id: "tc_metrics", name: "get_metrics", args: { service: "api" }, status: "running" } };
    await sleep(300, signal);
    yield {
      type: "tool_call",
      tool_call: {
        id: "tc_metrics",
        name: "get_metrics",
        args: { service: "api" },
        status: "done",
        result: JSON.stringify({ p99_ms: 184, error_rate: 0.012, restarts: 1 }),
      },
    };

    await sleep(120, signal);
    yield {
      type: "approval_request",
      approval: {
        id: "ap_restart",
        tool: "restart_service",
        args: { service: "api", reason: "error rate above 1% for 10m" },
        reason: "restarts production traffic — confirm before executing",
      },
    };
  }

  /** Tail of the canned run, resumed with the approval decision. */
  private async *runTail(
    decision: ApprovalResponse,
    question: string,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatEvent, string> {
    const q = question.trim() || "status";
    if (decision.approved) {
      await sleep(150, signal);
      yield { type: "tool_call", tool_call: { id: "tc_restart", name: "restart_service", args: { service: "api" }, status: "running" } };
      await sleep(400, signal);
      yield {
        type: "tool_call",
        tool_call: { id: "tc_restart", name: "restart_service", args: { service: "api" }, status: "done", result: "exit 0, healthy after 18s" },
      };
      for (const word of "Restart completed; error rate is back under 0.1%. ".split(" ")) {
        await sleep(10, signal);
        yield { type: "text_delta", delta: `${word} ` };
      }
    } else {
      for (const word of "Understood — leaving the service up and watching the error rate. ".split(" ")) {
        await sleep(10, signal);
        yield { type: "text_delta", delta: `${word} ` };
      }
    }

    await sleep(80, signal);
    yield { type: "usage", usage: { tokens: 640 + Math.ceil(q.length / 4), cost: 0.02 } };
    const answer = decision.approved
      ? `Restarted the api service for “${q}”; p99 and error rate recovered.`
      : `Skipped the restart for “${q}”; the service is stable and I'm monitoring it.`;
    yield {
      type: "done",
      done: {
        answer,
        citations: [
          { source: "runbook/incident-triage.md", locator: "§ restart policy", snippet: "restart when error rate > 1% for 10m" },
          { source: "metrics/dashboard", locator: "api / 1h", snippet: "p99 184ms, error rate 1.2%" },
        ],
        uncertainty: "single runbook source — no deploy diff in the window",
      },
    };
    return answer;
  }

  async listConversations(): Promise<ConversationMeta[]> {
    return [...this.conversations.values()]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map(({ messages: _messages, ...meta }) => meta);
  }

  async createConversation(title?: string): Promise<ConversationMeta> {
    const id = this.ensureConversation(title ?? "new conversation");
    const { messages: _messages, ...meta } = this.conversations.get(id)!;
    return meta;
  }

  async getConversation(id: string): Promise<Conversation> {
    const conv = this.conversations.get(id);
    if (!conv) throw new Error(`unknown conversation: ${id}`);
    return conv;
  }

  async renameConversation(id: string, title: string): Promise<ConversationMeta> {
    const conv = this.conversations.get(id);
    if (!conv) throw new Error(`unknown conversation: ${id}`);
    conv.title = title;
    conv.updated_at = new Date().toISOString();
    const { messages: _messages, ...meta } = conv;
    return meta;
  }

  async deleteConversation(id: string): Promise<void> {
    this.conversations.delete(id);
  }
}
