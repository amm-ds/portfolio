/**
 * Scripted mock transport for dev mode (VITE_MOCK=1): same ChatApi surface as
 * the HTTP client, backed by in-memory conversations and a canned agent run
 * (plan → search → metrics → approval-gated restart → answer). Mirrors the
 * backend's resume contract: the stream parks on approval_request until
 * decideApproval is called, then the SAME stream emits approval_response and
 * the rest of the run — no reconnect.
 */
import type { ChatEvent } from "./events";
import type { ChatApi, ChatRequest, Conversation, ConversationMeta, HealthInfo } from "./client";

/** The canned approval's id, echoed by approval_request/response and decideApproval. */
const APPROVAL_ID = "ap_restart";

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
  /** The approval the current run is parked on, answered by decideApproval. */
  private pending: { approvalId: string; resolve: (approved: boolean) => void } | null = null;
  private seq = 0;

  constructor() {
    this.seed();
  }

  private seed(): void {
    const now = new Date(0).toISOString();
    this.conversations.set("mock-welcome", {
      id: "mock-welcome",
      title: "example: incident triage",
      updatedAt: now,
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
    const question = req.message;
    const conversationId = req.conversation_id ?? this.ensureConversation(question);

    yield* this.runHead(question, signal);

    // Park exactly like the backend's ApprovalHub: the stream stays open until
    // the client POSTs the decision, then resumes on this same stream.
    const approved = await this.waitForApproval(signal);
    yield { type: "approval_response", approval_id: APPROVAL_ID, approved };
    const answer = yield* this.runTail(approved, question, signal);

    const conv = this.conversations.get(conversationId);
    if (conv) {
      conv.messages = [
        ...conv.messages,
        { role: "user", content: question },
        { role: "assistant", content: answer },
      ];
      conv.updatedAt = new Date().toISOString();
    }
    yield {
      type: "done",
      answer: {
        text: answer,
        citations: [
          { source: "runbook/incident-triage.md", quote: "restart when error rate > 1% for 10m" },
          { source: "metrics/dashboard", quote: "p99 184ms, error rate 1.2% (api / 1h)" },
        ],
        uncertainty: "medium",
      },
      usage: { input_tokens: 480, output_tokens: 160 + Math.ceil(question.length / 4), requests: 4 },
      conversation_id: conversationId,
    };
  }

  async decideApproval(approvalId: string, approved: boolean): Promise<void> {
    const pending = this.pending;
    this.pending = null;
    if (!pending || pending.approvalId !== approvalId) {
      throw new Error(`no pending approval ${approvalId}`);
    }
    pending.resolve(approved);
  }

  private waitForApproval(signal?: AbortSignal): Promise<boolean> {
    return new Promise((resolve, reject) => {
      this.pending = { approvalId: APPROVAL_ID, resolve };
      signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), {
        once: true,
      });
    });
  }

  private ensureConversation(title: string): string {
    const id = `mock-${++this.seq}`;
    const now = new Date().toISOString();
    this.conversations.set(id, {
      id,
      title: title.slice(0, 40) || "new conversation",
      updatedAt: now,
      messages: [],
    });
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
    yield { type: "tool_call_start", call_id: "tc_search", name: "search_docs", args: { q: q.slice(0, 60) } };
    await sleep(300, signal);
    yield {
      type: "tool_call_end",
      call_id: "tc_search",
      name: "search_docs",
      result: JSON.stringify({ hits: 2, top: ["runbook/incident-triage.md", "runbook/deploys.md"] }),
    };

    for (const word of "The runbook points at the api service. Pulling live metrics before touching anything. ".split(" ")) {
      await sleep(10, signal);
      yield { type: "text_delta", delta: `${word} ` };
    }
    await sleep(200, signal);
    yield { type: "tool_call_start", call_id: "tc_metrics", name: "get_metrics", args: { service: "api" } };
    await sleep(300, signal);
    yield {
      type: "tool_call_end",
      call_id: "tc_metrics",
      name: "get_metrics",
      result: JSON.stringify({ p99_ms: 184, error_rate: 0.012, restarts: 1 }),
    };

    await sleep(120, signal);
    yield {
      type: "approval_request",
      approval_id: APPROVAL_ID,
      tool: "restart_service",
      summary: "restarts production traffic — confirm before executing",
    };
  }

  /** Tail of the canned run, resumed with the approval decision. */
  private async *runTail(
    approved: boolean,
    question: string,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatEvent, string> {
    const q = question.trim() || "status";
    if (approved) {
      await sleep(150, signal);
      yield { type: "tool_call_start", call_id: "tc_restart", name: "restart_service", args: { service: "api" } };
      await sleep(400, signal);
      yield { type: "tool_call_end", call_id: "tc_restart", name: "restart_service", result: "exit 0, healthy after 18s" };
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

    return approved
      ? `Restarted the api service for “${q}”; p99 and error rate recovered.`
      : `Skipped the restart for “${q}”; the service is stable and I'm monitoring it.`;
  }

  async listConversations(): Promise<ConversationMeta[]> {
    return [...this.conversations.values()]
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
      .map(({ id, title, updatedAt, messages }) => ({
        id,
        title,
        updatedAt,
        messageCount: messages.length,
      }));
  }

  async getConversation(id: string): Promise<Conversation> {
    const conv = this.conversations.get(id);
    if (!conv) throw new Error(`unknown conversation: ${id}`);
    return conv;
  }

  async deleteConversation(id: string): Promise<void> {
    this.conversations.delete(id);
  }
}
