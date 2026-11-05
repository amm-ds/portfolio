import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ApprovalResponse, ChatEvent } from "../../lib/chat/events";
import type { ChatApi, ChatRequest, Conversation, ConversationMeta, HealthInfo } from "../../lib/chat/client";
import { useChat } from "../../lib/chat/useChat";
import { ChatSurface } from "./ChatSurface";

/** Stub transport replaying a two-leg scripted run (approval in the middle),
 *  mirroring the backend contract: the first stream ends after the
 *  approval_request; the resumed stream carries the rest. */
class StubChatApi implements ChatApi {
  requests: ChatRequest[] = [];
  private conversations = new Map<string, Conversation>();
  private seq = 0;

  constructor(
    private leg1: ChatEvent[],
    private leg2: ChatEvent[],
  ) {}

  async health(): Promise<HealthInfo> {
    return { status: "ok", model: "stub-model", provider: "stub" };
  }

  async *streamChat(req: ChatRequest): AsyncIterable<ChatEvent> {
    this.requests.push(req);
    const leg = req.approval_response ? this.leg2 : this.leg1;
    for (const event of leg) {
      await new Promise((r) => setTimeout(r, 0));
      yield event;
    }
  }

  async listConversations(): Promise<ConversationMeta[]> {
    return [...this.conversations.values()].map(({ messages: _m, ...meta }) => meta);
  }

  async createConversation(title?: string): Promise<ConversationMeta> {
    const id = `c${++this.seq}`;
    const now = new Date(0).toISOString();
    const conv: Conversation = { id, title: title ?? "new conversation", created_at: now, updated_at: now, messages: [] };
    this.conversations.set(id, conv);
    const { messages: _m, ...meta } = conv;
    return meta;
  }

  async getConversation(id: string): Promise<Conversation> {
    return this.conversations.get(id) ?? Promise.reject(new Error("not found"));
  }

  async renameConversation(id: string, title: string): Promise<ConversationMeta> {
    const conv = this.conversations.get(id)!;
    conv.title = title;
    const { messages: _m, ...meta } = conv;
    return meta;
  }

  async deleteConversation(): Promise<void> {}
}

const leg1: ChatEvent[] = [
  { type: "text_delta", delta: "Plan: check the runbook " },
  { type: "text_delta", delta: "and the metrics." },
  { type: "tool_call", tool_call: { id: "t1", name: "search_docs", args: { q: "p99" }, status: "running" } },
  {
    type: "tool_call",
    tool_call: { id: "t1", name: "search_docs", args: { q: "p99" }, status: "done", result: '{"hits": 2}' },
  },
  {
    type: "approval_request",
    approval: { id: "ap1", tool: "restart_service", args: { service: "api" }, reason: "production impact" },
  },
];

const leg2: ChatEvent[] = [
  { type: "text_delta", delta: "Restarting now." },
  { type: "usage", usage: { tokens: 812, cost: 0.02 } },
  {
    type: "done",
    done: {
      answer: "Restarted the api service; p99 recovered.",
      citations: [{ source: "runbook/incident-triage.md", locator: "§ restart policy" }],
    },
  },
];

function Harness({ api }: { api: ChatApi }) {
  const chat = useChat(api);
  return <ChatSurface chat={chat} />;
}

describe("ChatSurface scripted conversation", () => {
  it("runs plan → tool call → approval → answer end to end", async () => {
    const api = new StubChatApi(leg1, leg2);
    const user = userEvent.setup();
    render(<Harness api={api} />);

    await user.type(screen.getByLabelText("message"), "why did p99 spike?");
    await user.click(screen.getByRole("button", { name: "send" }));

    // Tool call card renders with its result (name also appears in the step
    // timeline, so scope to the card body).
    expect(await screen.findByText('{"hits": 2}')).toBeInTheDocument();
    expect(document.querySelector(".tool-name")).toHaveTextContent("search_docs");
    expect(screen.getByText("done")).toBeInTheDocument(); // tool state

    // Approval prompt is actionable once the run parks for approval.
    const approval = screen.getByRole("group", { name: "approval: restart_service" });
    expect(approval).toHaveTextContent("production impact");
    await screen.findByText("awaiting_approval"); // phase badge in the titlebar
    await user.click(screen.getByRole("button", { name: "approve" }));

    // Resumed run commits the answer, citations, and usage.
    expect(await screen.findByText("Restarted the api service; p99 recovered.")).toBeInTheDocument();
    expect(screen.getByText("runbook/incident-triage.md · § restart policy")).toBeInTheDocument();
    expect(screen.getByText(/812 tok/)).toBeInTheDocument();

    // The approval leg carried the operator's decision to the backend.
    const approvalLeg = api.requests.find((r) => r.approval_response);
    expect(approvalLeg?.approval_response).toEqual({ id: "ap1", approved: true } as ApprovalResponse);
  }, 10_000);
});
