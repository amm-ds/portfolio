/**
 * Chat state container: conversations, the active run's event log (folded to
 * parts for rendering), usage, health, and the approval resume cycle.
 *
 * Approval flow: the backend ends the SSE stream after `approval_request`;
 * the hook flips to "awaiting_approval", then `respondApproval` re-posts
 * /chat with the decision and keeps folding events into the same run.
 *
 * Assistant turns commit as { content, parts, citations?, uncertainty? } so
 * tool cards and sources stay visible after the run ends; turns loaded from
 * the backend history (content only) render as plain markdown.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApprovalResponse, Citation, ChatEvent, Usage } from "./events";
import type { ChatApi, ChatMessage, ConversationMeta, HealthInfo } from "./client";
import { reduceEvents } from "./parts";
import type { Part } from "./parts";

export type RunPhase = "idle" | "streaming" | "awaiting_approval";

export interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  parts?: Part[];
  citations?: Citation[];
  uncertainty?: string;
}

export interface ChatState {
  conversations: ConversationMeta[];
  activeId: string | null;
  /** Committed history of the active conversation. */
  messages: DisplayMessage[];
  /** Live run events and their fold; empty when no run is in flight. */
  events: ChatEvent[];
  parts: Part[];
  phase: RunPhase;
  usage: Usage | null;
  health: HealthInfo | null;
  error: string | null;
}

const initialState: ChatState = {
  conversations: [],
  activeId: null,
  messages: [],
  events: [],
  parts: [],
  phase: "idle",
  usage: null,
  health: null,
  error: null,
};

const toWire = (messages: DisplayMessage[]): ChatMessage[] =>
  messages.map(({ role, content }) => ({ role, content }));

export function useChat(api: ChatApi) {
  const [state, setState] = useState<ChatState>(initialState);
  const abortRef = useRef<AbortController | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const historyRef = useRef<DisplayMessage[]>([]);
  const runEventsRef = useRef<ChatEvent[]>([]);
  activeIdRef.current = state.activeId;
  historyRef.current = state.messages;

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const startRun = useCallback(
    async (history: DisplayMessage[], approvalResponse?: ApprovalResponse) => {
      const controller = new AbortController();
      abortRef.current = controller;

      // Fold the operator decision in immediately so the approval card shows
      // its state before the resumed stream starts (idempotent if echoed).
      const events: ChatEvent[] = approvalResponse
        ? [...runEventsRef.current, { type: "approval_response", approval: approvalResponse }]
        : [];
      runEventsRef.current = events;
      setState((s) => ({ ...s, phase: "streaming", error: null, events, parts: reduceEvents(events) }));

      try {
        for await (const event of api.streamChat(
          { conversation_id: activeIdRef.current ?? undefined, messages: toWire(history), approval_response: approvalResponse },
          controller.signal,
        )) {
          events.push(event);
          const patch =
            event.type === "usage"
              ? { events: [...events], parts: reduceEvents(events), usage: event.usage }
              : { events: [...events], parts: reduceEvents(events) };
          setState((s) => ({ ...s, ...patch }));
        }
        const done = events.find((e) => e.type === "done");
        const pendingApproval = reduceEvents(events).some(
          (p) => p.kind === "approval" && p.approval.status === "pending",
        );
        if (done && done.type === "done") {
          // The polished answer supersedes the last streamed text fragment.
          const committed = reduceEvents(events);
          if (done.done.answer !== "") {
            let lastText = -1;
            committed.forEach((p, i) => {
              if (p.kind === "text") lastText = i;
            });
            const answerPart: Part = { kind: "text", text: done.done.answer };
            if (lastText === -1) committed.push(answerPart);
            else committed[lastText] = answerPart;
          }
          runEventsRef.current = [];
          setState((s) => ({
            ...s,
            messages: [
              ...history,
              {
                role: "assistant",
                content: done.done.answer,
                parts: committed,
                citations: done.done.citations.length > 0 ? done.done.citations : undefined,
                uncertainty: done.done.uncertainty,
              },
            ],
            events: [],
            parts: [],
            phase: "idle",
          }));
        } else {
          setState((s) => ({ ...s, phase: pendingApproval ? "awaiting_approval" : "idle" }));
        }
        void api.listConversations().then(
          (conversations) => setState((s) => ({ ...s, conversations })),
          () => undefined,
        );
      } catch (error) {
        if (controller.signal.aborted) {
          setState((s) => ({ ...s, phase: "idle" }));
        } else {
          setState((s) => ({
            ...s,
            phase: "idle",
            error: error instanceof Error ? error.message : String(error),
          }));
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
      }
    },
    [api],
  );

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (content === "" || state.phase !== "idle") return;

      // Ensure a conversation exists so the backend can persist against it.
      let conversationId = activeIdRef.current;
      if (conversationId === null) {
        const meta = await api.createConversation(content.slice(0, 40));
        conversationId = meta.id;
        setState((s) => ({ ...s, conversations: [meta, ...s.conversations], activeId: meta.id }));
      }

      const history = [...historyRef.current, { role: "user", content } as DisplayMessage];
      runEventsRef.current = [];
      setState((s) => ({ ...s, activeId: conversationId, messages: history, events: [], parts: [] }));
      void startRun(history);
    },
    [api, startRun, state.phase],
  );

  const respondApproval = useCallback(
    (id: string, approved: boolean) => {
      if (state.phase !== "awaiting_approval") return;
      void startRun(historyRef.current, { id, approved });
    },
    [startRun, state.phase],
  );

  const select = useCallback(
    async (id: string) => {
      stop();
      runEventsRef.current = [];
      setState((s) => ({ ...s, activeId: id, events: [], parts: [], usage: null, error: null, phase: "idle" }));
      try {
        const conv = await api.getConversation(id);
        setState((s) => ({ ...s, messages: conv.messages }));
      } catch (error) {
        setState((s) => ({
          ...s,
          error: error instanceof Error ? error.message : String(error),
          messages: [],
        }));
      }
    },
    [api, stop],
  );

  const create = useCallback(async () => {
    stop();
    const meta = await api.createConversation("new conversation");
    runEventsRef.current = [];
    setState((s) => ({
      ...s,
      conversations: [meta, ...s.conversations],
      activeId: meta.id,
      messages: [],
      events: [],
      parts: [],
      usage: null,
      phase: "idle",
      error: null,
    }));
  }, [api, stop]);

  const rename = useCallback(
    async (id: string, title: string) => {
      const meta = await api.renameConversation(id, title);
      setState((s) => ({ ...s, conversations: s.conversations.map((c) => (c.id === id ? meta : c)) }));
    },
    [api],
  );

  const remove = useCallback(
    async (id: string) => {
      await api.deleteConversation(id);
      setState((s) => {
        const cleared = s.activeId === id;
        return {
          ...s,
          conversations: s.conversations.filter((c) => c.id !== id),
          activeId: cleared ? null : s.activeId,
          messages: cleared ? [] : s.messages,
          events: cleared ? [] : s.events,
          parts: cleared ? [] : s.parts,
          phase: cleared ? "idle" : s.phase,
        };
      });
    },
    [api],
  );

  useEffect(() => {
    let cancelled = false;
    void api.health().then(
      (health) => !cancelled && setState((s) => ({ ...s, health })),
      () => !cancelled && setState((s) => ({ ...s, health: { status: "unreachable" } })),
    );
    void api.listConversations().then(
      (conversations) => {
        if (cancelled || conversations.length === 0) return;
        setState((s) => ({ ...s, conversations }));
        void select(conversations[0].id);
      },
      () => undefined,
    );
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [api, select]);

  return {
    state,
    send,
    stop,
    select,
    create,
    rename,
    remove,
    respondApproval,
    awaitingApproval: state.phase === "awaiting_approval",
  };
}

export type ChatController = ReturnType<typeof useChat>;
