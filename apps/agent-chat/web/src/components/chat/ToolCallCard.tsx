import type { ToolCallState } from "../../lib/chat/parts";

const STATUS_LABEL: Record<ToolCallState["status"], string> = {
  running: "running",
  done: "done",
};

/** One tool invocation: status timeline + collapsible args JSON + result. */
export function ToolCallCard({ call }: { call: ToolCallState }) {
  return (
    <div className={`tool-card tool-card--${call.status}`}>
      <div className="tool-card-head">
        <span className={`tool-status tool-status--${call.status}`} aria-hidden="true">
          {call.status === "running" ? "▸" : "✓"}
        </span>
        <span className="tool-name">{call.name}</span>
        <span className="tool-state">{STATUS_LABEL[call.status]}</span>
      </div>
      <details className="tool-args">
        <summary>args</summary>
        <pre>
          <code>{JSON.stringify(call.args, null, 2)}</code>
        </pre>
      </details>
      {call.result !== undefined && (
        <pre className="tool-result">
          <code>{call.result}</code>
        </pre>
      )}
    </div>
  );
}
