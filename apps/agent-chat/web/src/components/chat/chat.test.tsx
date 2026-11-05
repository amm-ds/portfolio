import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ChatEvent } from "../../lib/chat/events";
import type { ChatApi, ChatRequest, Conversation, ConversationMeta, HealthInfo } from "../../lib/chat/client";
import { useChat } from "../../lib/chat/useChat";
import { ChatSurface } from "./ChatSurface";

/** Stub transport mirroring the backend's real flow: ONE stream parks after
 *  approval_request and resumes in place when decideApproval POSTs the
 *  decision — no second request, no reconnect. */
class StubChatApi implements ChatApi {
  requests: ChatRequest[] = [];
  decisions: { approvalId: string; approved: boolean }[] = [];
  private resolveApproval: ((decision: { approvalId: string; approved: boolean }) => void) | null = null;

  constructor(
    private head: ChatEvent[],
    private tail: (decision: { approvalId: string; approved: boolean }) => ChatEvent[],
  ) {}

  async health(): Promise<HealthInfo> {
    return { status: "ok", model: "stub-model", provider: "stub" };
  }

  async *streamChat(req: ChatRequest): AsyncIterable<ChatEvent> {
    this.requests.push(req);
    for (const event of this.head) {
      await new Promise((r) => setTimeout(r, 0));
      yield event;
    }
    const decision = await new Promise<{ approvalId: string; approved: boolean }>((resolve) => {
      this.resolveApproval = resolve;
    });
    this.decisions.push(decision);
    for (const event of this.tail(decision)) {
      await new Promise((r) => setTimeout(r, 0));
      yield event;
    }
  }

  async decideApproval(approvalId: string, approved: boolean): Promise<void> {
    if (!this.resolveApproval) throw new Error("no pending approval");
    this.resolveApproval({ approvalId, approved });
  }

  async listConversations(): Promise<ConversationMeta[]> {
    return [];
  }

  async getConversation(): Promise<Conversation> {
    throw new Error("not found");
  }

  async deleteConversation(): Promise<void> {}
}

const head: ChatEvent[] = [
  { type: "text_delta", delta: "Plan: check the runbook " },
  { type: "text_delta", delta: "and the metrics." },
  { type: "tool_call_start", call_id: "t1", name: "search_docs", args: { q: "p99" } },
  { type: "tool_call_end", call_id: "t1", name: "search_docs", result: '{"hits": 2}' },
  {
    type: "approval_request",
    approval_id: "ap1",
    tool: "restart_service",
    summary: "production impact",
  },
];

const tail = (decision: { approvalId: string; approved: boolean }): ChatEvent[] => [
  { type: "approval_response", approval_id: decision.approvalId, approved: decision.approved },
  { type: "text_delta", delta: "Restarting now." },
  {
    type: "done",
    answer: {
      text: "Restarted the api service; p99 recovered.",
      citations: [{ source: "runbook/incident-triage.md", quote: "restart when error rate > 1%" }],
      uncertainty: "low",
    },
    usage: { input_tokens: 800, output_tokens: 12, requests: 3 },
    conversation_id: "conv-1",
  },
];

function Harness({ api }: { api: ChatApi }) {
  const chat = useChat(api);
  return <ChatSurface chat={chat} />;
}

describe("ChatSurface scripted conversation", () => {
  it("runs plan → tool call → approval → answer end to end", async () => {
    const api = new StubChatApi(head, tail);
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

    // The resumed run commits the answer, citations, and usage.
    expect(await screen.findByText("Restarted the api service; p99 recovered.")).toBeInTheDocument();
    expect(screen.getByText("runbook/incident-triage.md · “restart when error rate > 1%”")).toBeInTheDocument();
    expect(screen.getByText(/812 tok/)).toBeInTheDocument();

    // The decision went out on the approval leg; the run was ONE request.
    expect(api.decisions).toEqual([{ approvalId: "ap1", approved: true }]);
    expect(api.requests).toHaveLength(1);
    expect(api.requests[0]).toEqual({ message: "why did p99 spike?" });
  }, 10_000);
});
