import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../workbench/useWorkbench";
import type { SelectedCitation } from "../workbench/useWorkbench";
import { EvidenceChips } from "./EvidenceChips";

export function PageChatMode({
  pageNumber,
  history,
  sending,
  error,
  onSend,
  onRetry,
  onReveal,
}: {
  pageNumber: number;
  history: ChatMessage[];
  sending: boolean;
  error: { page: number; message: string } | null;
  onSend: (page: number, content: string) => void;
  onRetry: (page: number) => void;
  onReveal: (citation: SelectedCitation) => void;
}) {
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [history.length, sending]);

  const submit = () => {
    const trimmed = draft.trim();
    if (!trimmed || sending) return;
    onSend(pageNumber, trimmed);
    setDraft("");
  };

  return (
    <div className="chat-mode">
      <p className="chat-mode__note">
        Ask about page {pageNumber} only. Answers cite this page; chat history is kept in memory and never
        changes the analysis.
      </p>
      <div className="chat-log" ref={logRef} role="log" aria-live="polite" aria-label={`Conversation about page ${pageNumber}`}>
        {history.length === 0 ? (
          <p className="muted mode-empty">
            No questions yet. Ask something specific about page {pageNumber}.
          </p>
        ) : null}
        {history.map((message, index) => (
          <article key={index} className={`chat-bubble chat-bubble--${message.role}`}>
            <span className="chat-bubble__role">{message.role === "user" ? "you" : "assistant"}</span>
            <p className="chat-bubble__text">{message.content}</p>
            {message.citations && message.citations.length > 0 ? (
              <EvidenceChips
                evidence={message.citations}
                label={`Answer ${index + 1}`}
                onReveal={onReveal}
              />
            ) : null}
          </article>
        ))}
        {sending ? (
          <div className="chat-loading" role="status">
            <span className="spinner" aria-hidden="true" />
            Reading page {pageNumber}…
          </div>
        ) : null}
      </div>
      {error && error.page === pageNumber ? (
        <div className="chat-error" role="alert">
          <span>
            <strong>Answer failed.</strong> {error.message}
          </span>
          <button type="button" className="button button--small" onClick={() => onRetry(pageNumber)}>
            Retry
          </button>
        </div>
      ) : null}
      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label htmlFor="page-question" className="sr-only">Ask about page {pageNumber}</label>
        <textarea
          id="page-question"
          rows={3}
          maxLength={2000}
          value={draft}
          disabled={sending}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={`Ask about page ${pageNumber}…`}
        />
        <div className="chat-composer__actions">
          <span>{draft.length}/2000</span>
          <button type="submit" className="button button--primary" disabled={sending || !draft.trim()}>
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
