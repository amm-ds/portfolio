/**
 * Chat state container: conversations, the active run's event log (folded to
 * parts for rendering), usage, health, and the approval cycle.
 *
 * Approval flow (mirrors the backend, routes_chat.py): the run's SSE stream
 * stays OPEN while parked on `approval_request` — the hook flips to
 * "awaiting_approval", then `respondApproval` POSTs the decision to
 * /approvals/{id}; the server emits `approval_response` on the same stream and
 * the run resumes. There is no reconnect or resume token.
 *
 * The backend persists each run itself and returns its conversation id in the
 * `done` event, so "+ new" is a purely local action: the conversation comes
 * into existence with the first completed run. Turns loaded from history
 * (content only) render as plain markdown.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Citation, ChatEvent, Usage } from "./events";
import type { ChatApi, ConversationMeta, HealthInfo } from "./client";
import { commitFinalAnswer, reduceEvents } from "./parts";
import type { Part } from "./parts";

export type RunPhase = "idle" | "streaming" | "awaiting_approval";

export interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  parts?: Part[];
  citations?: Citation[];
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
    async (history: DisplayMessage[]) => {
      const message = [...history].reverse().find((m) => m.role === "user");
      if (!message) return;
      const controller = new AbortController();
      abortRef.current = controller;

      const events: ChatEvent[] = [];
      runEventsRef.current = events;
      // Clear the previous run's usage so observers cannot mistake it for completion.
      setState((s) => ({ ...s, phase: "streaming", usage: null, error: null, events, parts: [] }));

      try {
        for await (const event of api.streamChat(
          { message: message.content, conversation_id: activeIdRef.current ?? undefined },
          controller.signal,
        )) {
          events.push(event);
          const parts = reduceEvents(events);
          const patch: Partial<ChatState> = { events: [...events], parts };
          if (event.type === "approval_request") {
            // The stream stays open, parked until decideApproval is answered.
            patch.phase = "awaiting_approval";
          } else if (event.type === "approval_response") {
            patch.phase = "streaming";
          } else if (event.type === "done") {
            patch.usage = event.usage;
          } else if (event.type === "error") {
            patch.error = `${event.code}: ${event.message}`;
          }
          setState((s) => ({ ...s, ...patch }));
        }
        const done = events.find((e) => e.type === "done");
        if (done && done.type === "done") {
          // The atomic answer supersedes every trailing streamed fragment;
          // tool/approval parts and earlier plan/critique text remain intact.
          const streamed = reduceEvents(events);
          const committed = done.answer.text === ""
            ? streamed
            : commitFinalAnswer(streamed, done.answer.text);
          runEventsRef.current = [];
          setState((s) => ({
            ...s,
            activeId: done.conversation_id,
            messages: [
              ...history,
              {
                role: "assistant",
                content: done.answer.text,
                parts: committed,
                citations: done.answer.citations.length > 0 ? done.answer.citations : undefined,
              },
            ],
            events: [],
            parts: [],
            phase: "idle",
          }));
        } else {
          const pendingApproval = reduceEvents(events).some(
            (p) => p.kind === "approval" && p.approval.status === "pending",
          );
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

      // No conversation pre-creation: the backend persists the run itself and
      // returns the new conversation id in the done event.
      const history = [...historyRef.current, { role: "user", content } as DisplayMessage];
      runEventsRef.current = [];
      setState((s) => ({ ...s, messages: history, events: [], parts: [] }));
      void startRun(history);
    },
    [startRun, state.phase],
  );

  const respondApproval = useCallback(
    (id: string, approved: boolean) => {
      if (state.phase !== "awaiting_approval") return;
      // Fold the operator decision in immediately so the approval card shows
      // its state before the echoed approval_response arrives (idempotent).
      const events = [...runEventsRef.current, { type: "approval_response", approval_id: id, approved } as ChatEvent];
      runEventsRef.current = events;
      setState((s) => ({ ...s, phase: "streaming", events, parts: reduceEvents(events) }));
      void api.decideApproval(id, approved).catch((error: unknown) => {
        setState((s) => ({
          ...s,
          phase: "streaming",
          error: error instanceof Error ? error.message : String(error),
        }));
      });
    },
    [api, state.phase],
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

  const create = useCallback(() => {
    stop();
    runEventsRef.current = [];
    setState((s) => ({
      ...s,
      activeId: null,
      messages: [],
      events: [],
      parts: [],
      usage: null,
      phase: "idle",
      error: null,
    }));
  }, [stop]);

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
    remove,
    respondApproval,
    awaitingApproval: state.phase === "awaiting_approval",
  };
}

export type ChatController = ReturnType<typeof useChat>;
