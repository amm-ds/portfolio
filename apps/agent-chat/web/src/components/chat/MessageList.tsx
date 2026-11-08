import { useEffect, useRef } from "react";
import type { Part } from "../../lib/chat/parts";
import type { DisplayMessage } from "../../lib/chat/useChat";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: DisplayMessage[];
  /** Parts of the in-flight run; rendered after the committed messages. */
  liveParts: Part[];
  awaitingApproval: boolean;
  onRespondApproval: (id: string, approved: boolean) => void;
}

export function MessageList({ messages, liveParts, awaitingApproval, onRespondApproval }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    const latest = el?.querySelector<HTMLElement>(".bubble:last-of-type");
    // Keep the newest complete bubble in view; absolute-bottom scrolling can
    // leave its first lines clipped when a run emits several parts at once.
    if (latest && typeof latest.scrollIntoView === "function") {
      latest.scrollIntoView({ block: "nearest" });
    }
  }, [messages, liveParts]);

  return (
    <div className="message-list" ref={scrollRef}>
      {messages.length === 0 && liveParts.length === 0 && (
        <div className="chat-empty">
          <p className="chat-empty-cmd">agent-chat — ask anything</p>
          <p className="chat-empty-hint">
            The agent plans, calls tools, and asks before consequential actions. Try “why did p99 spike?”
          </p>
        </div>
      )}
      {messages.map((message, i) => (
        <MessageBubble
          key={i}
          from={message.role}
          content={message.content}
          parts={message.parts}
          citations={message.citations}
          locked={!awaitingApproval}
          onRespondApproval={onRespondApproval}
        />
      ))}
      {liveParts.length > 0 && (
        <MessageBubble
          from="assistant"
          content=""
          parts={liveParts}
          locked={!awaitingApproval}
          onRespondApproval={onRespondApproval}
        />
      )}
    </div>
  );
}
