import { useState } from "react";
import type { ChatController } from "../../lib/chat/useChat";
import { AgentSteps } from "./AgentSteps";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";

/** App shell: conversation sidebar + main chat pane. */
export function ChatSurface({ chat }: { chat: ChatController }) {
  const { state, send, stop, select, create, rename, remove, respondApproval } = chat;
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");

  const commitRename = async (id: string) => {
    const title = draftTitle.trim();
    setEditingId(null);
    if (title !== "") await rename(id, title);
  };

  return (
    <div className="chat-app">
      <aside className="chat-sidebar">
        <div className="sidebar-head">
          <span className="sidebar-title">conversations</span>
          <button type="button" className="btn btn-new" onClick={() => void create()}>
            + new
          </button>
        </div>
        <ul className="conversation-list">
          {state.conversations.length === 0 && <li className="conversation-empty">none yet</li>}
          {state.conversations.map((conv) => (
            <li key={conv.id} className={`conversation-item${conv.id === state.activeId ? " active" : ""}`}>
              {editingId === conv.id ? (
                <input
                  className="conversation-rename"
                  value={draftTitle}
                  aria-label="rename conversation"
                  ref={(el) => el?.focus()}
                  onChange={(e) => setDraftTitle(e.target.value)}
                  onBlur={() => void commitRename(conv.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void commitRename(conv.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                />
              ) : (
                <>
                  <button
                    type="button"
                    className="conversation-select"
                    aria-current={conv.id === state.activeId ? "true" : undefined}
                    onClick={() => void select(conv.id)}
                  >
                    {conv.title}
                  </button>
                  <button
                    type="button"
                    className="conversation-action"
                    aria-label={`rename ${conv.title}`}
                    onClick={() => {
                      setEditingId(conv.id);
                      setDraftTitle(conv.title);
                    }}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className="conversation-action"
                    aria-label={`delete ${conv.title}`}
                    onClick={() => void remove(conv.id)}
                  >
                    ×
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </aside>

      <main className="chat-main">
        <div className="chat-titlebar">
          <span className="terminal-dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className="chat-title">agent-chat</span>
          <span className="chat-phase">{state.phase}</span>
        </div>
        {state.error && <p className="chat-error" role="alert">error: {state.error}</p>}
        <AgentSteps parts={state.parts} running={state.phase === "streaming"} />
        <MessageList
          messages={state.messages}
          liveParts={state.parts}
          awaitingApproval={state.phase === "awaiting_approval"}
          onRespondApproval={respondApproval}
        />
        <Composer phase={state.phase} usage={state.usage} health={state.health} onSend={send} onStop={stop} />
      </main>
    </div>
  );
}
