import type { ApprovalState } from "../../lib/chat/parts";

interface Props {
  approval: ApprovalState;
  /** True while another run/selection owns the UI or a decision is in flight. */
  locked: boolean;
  onRespond: (id: string, approved: boolean) => void;
}

function outcome(approval: ApprovalState): string {
  switch (approval.status) {
    case "submitting":
      return "submitting decision…";
    case "approved":
      return approval.execution === "completed" ? "approved — executed" : "approved — executing";
    case "rejected":
      return "rejected — skipped";
    case "failed":
      return "decision failed — retry";
    case "pending":
      return "";
  }
}

/** Consequential-tool prompt: exact payload, explicit submission and execution state. */
export function ApprovalCard({ approval, locked, onRespond }: Props) {
  const canRespond = approval.status === "pending" || approval.status === "failed";
  const glyph = approval.status === "approved" ? "✓" : canRespond || approval.status === "submitting" ? "?" : "✗";
  return (
    <div className={`approval-card approval-card--${approval.status}`} role="group" aria-label={`approval: ${approval.tool}`}>
      <div className="approval-head">
        <span className="approval-glyph" aria-hidden="true">{glyph}</span>
        <span className="approval-tool">{approval.tool}</span>
        <span className="approval-state">{approval.status}</span>
      </div>
      {approval.summary && <p className="approval-reason">{approval.summary}</p>}
      <details className="approval-args">
        <summary>action payload</summary>
        <pre><code>{JSON.stringify(approval.payload, null, 2)}</code></pre>
      </details>
      {canRespond ? (
        <div className="approval-actions">
          <button type="button" className="btn btn-approve" disabled={locked} onClick={() => onRespond(approval.id, true)}>
            approve
          </button>
          <button type="button" className="btn btn-reject" disabled={locked} onClick={() => onRespond(approval.id, false)}>
            reject
          </button>
        </div>
      ) : (
        <p className="approval-outcome">{outcome(approval)}</p>
      )}
    </div>
  );
}
