/**
 * Chat state container: conversations, the active run's event log (folded to
 * parts for rendering), per-run usage, health, and the approval cycle.
 *
 * Approval decisions remain non-terminal until the server echoes them on the
 * run's SSE stream. Navigation invalidates the active run and any older history
 * load, so late events cannot overwrite a newly selected conversation.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Citation, ChatEvent, Usage } from "./events";
import type { ChatApi, ConversationMeta, HealthInfo } from "./client";
import { commitFinalAnswer, reduceEvents } from "./parts";
import type { LocalApprovalStatus, Part } from "./parts";

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
  /** Usage delta for the latest completed run, never conversation-cumulative. */
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
  const navigationRef = useRef(0);
  const runIdRef = useRef(0);
  const listMutationRef = useRef(0);
  const localApprovalStatusRef = useRef<Record<string, LocalApprovalStatus>>({});
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
      // Starting a run also invalidates any still-loading selected history.
      const navigation = ++navigationRef.current;
      const runId = ++runIdRef.current;
      const conversationId = activeIdRef.current ?? undefined;
      const isCurrent = () => navigationRef.current === navigation && runIdRef.current === runId;
      const events: ChatEvent[] = [];
      localApprovalStatusRef.current = {};
      runEventsRef.current = events;
      setState((s) => ({ ...s, phase: "streaming", usage: null, error: null, events, parts: [] }));

      try {
        for await (const event of api.streamChat(
          { message: message.content, conversation_id: conversationId },
          controller.signal,
        )) {
          if (!isCurrent()) return;
          events.push(event);
          if (event.type === "approval_response") {
            delete localApprovalStatusRef.current[event.approval_id];
          }
          const patch: Partial<ChatState> = {
            events: [...events],
            parts: reduceEvents(events, localApprovalStatusRef.current),
          };
          if (event.type === "approval_request") {
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
        if (!isCurrent()) return;
        if (controller.signal.aborted) {
          setState((s) => ({ ...s, phase: "idle" }));
          return;
        }
        const done = events.find((e) => e.type === "done");
        if (done && done.type === "done") {
          // The atomic answer supersedes every trailing streamed fragment;
          // tool/approval parts and earlier plan/critique text remain intact.
          const streamed = reduceEvents(events, localApprovalStatusRef.current);
          const committed = done.answer.text === ""
            ? streamed
            : commitFinalAnswer(streamed, done.answer.text);
          runEventsRef.current = [];
          localApprovalStatusRef.current = {};
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
          const pendingApproval = reduceEvents(events, localApprovalStatusRef.current).some(
            (p) => p.kind === "approval" && p.approval.status === "pending",
          );
          setState((s) => ({ ...s, phase: pendingApproval ? "awaiting_approval" : "idle" }));
        }
        const listMutation = listMutationRef.current;
        void api.listConversations().then(
          (conversations) => {
            if (isCurrent() && listMutationRef.current === listMutation) {
              setState((s) => ({ ...s, conversations }));
            }
          },
          () => undefined,
        );
      } catch (error) {
        if (!isCurrent()) return;
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
      if (content === "" || state.phase !== "idle" || abortRef.current !== null) return;

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
      if (
        state.phase !== "awaiting_approval" ||
        localApprovalStatusRef.current[id] === "submitting"
      ) return;
      localApprovalStatusRef.current[id] = "submitting";
      const events = runEventsRef.current;
      setState((s) => ({
        ...s,
        events: [...events],
        parts: reduceEvents(events, localApprovalStatusRef.current),
      }));
      void api.decideApproval(id, approved).catch((error: unknown) => {
        if (localApprovalStatusRef.current[id] !== "submitting") return;
        localApprovalStatusRef.current[id] = "failed";
        setState((s) => ({
          ...s,
          phase: "awaiting_approval",
          parts: reduceEvents(runEventsRef.current, localApprovalStatusRef.current),
          error: error instanceof Error ? error.message : String(error),
        }));
      });
    },
    [api, state.phase],
  );

  const select = useCallback(
    async (id: string) => {
      const navigation = ++navigationRef.current;
      stop();
      activeIdRef.current = id;
      historyRef.current = [];
      runEventsRef.current = [];
      localApprovalStatusRef.current = {};
      setState((s) => ({
        ...s,
        activeId: id,
        messages: [],
        events: [],
        parts: [],
        usage: null,
        error: null,
        phase: "idle",
      }));
      try {
        const conv = await api.getConversation(id);
        if (navigationRef.current === navigation) {
          setState((s) => ({ ...s, messages: conv.messages }));
        }
      } catch (error) {
        if (navigationRef.current !== navigation) return;
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
    navigationRef.current += 1;
    stop();
    activeIdRef.current = null;
    historyRef.current = [];
    runEventsRef.current = [];
    localApprovalStatusRef.current = {};
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
      const clearActive = activeIdRef.current === id;
      listMutationRef.current += 1;
      if (clearActive) {
        // Invalidate before awaiting DELETE so a late done cannot resurrect it.
        navigationRef.current += 1;
        stop();
        activeIdRef.current = null;
        historyRef.current = [];
        runEventsRef.current = [];
        localApprovalStatusRef.current = {};
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
      }
      try {
        await api.deleteConversation(id);
        setState((s) => ({
          ...s,
          conversations: s.conversations.filter((c) => c.id !== id),
        }));
      } catch (error) {
        setState((s) => ({
          ...s,
          error: error instanceof Error ? error.message : String(error),
        }));
      }
    },
    [api, stop],
  );

  useEffect(() => {
    let cancelled = false;
    void api.health().then(
      (health) => !cancelled && setState((s) => ({ ...s, health })),
      () => !cancelled && setState((s) => ({ ...s, health: { status: "unreachable" } })),
    );
    const listMutation = listMutationRef.current;
    const navigation = navigationRef.current;
    void api.listConversations().then(
      (conversations) => {
        if (
          cancelled ||
          conversations.length === 0 ||
          listMutationRef.current !== listMutation
        ) return;
        setState((s) => ({ ...s, conversations }));
        // A selection/new conversation made while the list was in flight wins.
        if (navigationRef.current === navigation && activeIdRef.current === null) {
          void select(conversations[0].id);
        }
      },
      () => undefined,
    );
    return () => {
      cancelled = true;
      navigationRef.current += 1;
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
