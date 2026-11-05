import { useRef, useState } from "react";
import type { HealthInfo } from "../../lib/chat/client";
import type { Usage } from "../../lib/chat/events";
import type { RunPhase } from "../../lib/chat/useChat";

const DEFAULT_BUDGET = 100_000;

interface Props {
  phase: RunPhase;
  usage: Usage | null;
  health: HealthInfo | null;
  budget?: number;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function Composer({ phase, usage, health, budget = DEFAULT_BUDGET, onSend, onStop }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const busy = phase !== "idle";

  const submit = () => {
    const text = value.trim();
    if (text === "" || busy) return;
    onSend(text);
    setValue("");
    textareaRef.current?.focus();
  };

  const ratio = usage ? Math.min((usage.input_tokens + usage.output_tokens) / budget, 1) : 0;
  const totalTokens = usage ? usage.input_tokens + usage.output_tokens : 0;

  return (
    <div className="composer">
      <div className="composer-meta">
        <span className="composer-badge" title={health ? `status: ${health.status}` : "health unknown"}>
          <span
            className={`status-dot status-dot--${health?.status === "ok" ? "ok" : "down"}`}
            aria-hidden="true"
          />
          {health?.model ?? "no model"}
          {health?.provider ? `@${health.provider}` : ""}
        </span>
        <span className="composer-meter" aria-label={usage ? `token usage ${totalTokens} of ${budget}` : "no usage yet"}>
          <span className="composer-meter-bar" style={{ width: `${Math.round(ratio * 100)}%` }} />
          <span className="composer-meter-text">
            {usage ? `${totalTokens.toLocaleString()} tok · ${usage.requests} req` : phase === "awaiting_approval" ? "awaiting approval…" : "idle"}
          </span>
        </span>
      </div>
      <div className="composer-row">
        <textarea
          ref={textareaRef}
          className="composer-input"
          value={value}
          rows={2}
          placeholder={busy ? "agent is working…" : "type a message · enter to send"}
          aria-label="message"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {phase === "streaming" ? (
          <button type="button" className="btn btn-stop" onClick={onStop}>
            stop
          </button>
        ) : (
          <button type="button" className="btn btn-send" disabled={busy || value.trim() === ""} onClick={submit}>
            send
          </button>
        )}
      </div>
    </div>
  );
}
