import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { HttpChatApi } from "./client";

const SESSION_ID = "123e4567-e89b-42d3-a456-426614174000";
let fetchMock: Mock<typeof fetch>;

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function requestHeaders(index: number): Record<string, string> {
  return (fetchMock.mock.calls[index][1]?.headers ?? {}) as Record<string, string>;
}

describe("HttpChatApi session headers", () => {
  it("scopes chat, approvals, and conversation requests without adding session fields to chat", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response("data: [DONE]\n\n"))
      .mockResolvedValueOnce(new Response(null))
      .mockResolvedValueOnce(new Response(JSON.stringify({ conversations: [] })))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            meta: { conversation_id: "conv-1", title: "Conversation", updated_at: "2026-01-01" },
            conversation: { messages: [] },
          }),
        ),
      )
      .mockResolvedValueOnce(new Response(null));
    const api = new HttpChatApi("http://example.test", { apiKey: "secret", sessionId: SESSION_ID });

    for await (const event of api.streamChat({ message: "hello", conversation_id: "conv-1" })) {
      throw new Error(`unexpected event: ${event.type}`);
    }
    await api.decideApproval("approval-1", true);
    await api.listConversations();
    await api.getConversation("conv-1");
    await api.deleteConversation("conv-1");

    expect(fetchMock).toHaveBeenCalledTimes(5);
    for (let index = 0; index < 5; index += 1) {
      expect(requestHeaders(index)).toMatchObject({ "x-agent-chat-session": SESSION_ID });
    }

    const chatBody = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as Record<string, unknown>;
    expect(chatBody).toEqual({ message: "hello", conversation_id: "conv-1" });
    expect(chatBody).not.toHaveProperty("user_id");
    expect(chatBody).not.toHaveProperty("session_id");
  });

  it("does not add the session header to health checks", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" })));
    const api = new HttpChatApi("", { apiKey: "secret", sessionId: SESSION_ID });

    await api.health();

    expect(requestHeaders(0)).toEqual({ "x-api-key": "secret" });
  });
});
