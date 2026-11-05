import type { ApprovalState } from "../../lib/chat/parts";

interface Props {
  approval: ApprovalState;
  /** True while the run is streaming (only the awaiting phase accepts input). */
  locked: boolean;
  onRespond: (id: string, approved: boolean) => void;
}

/** Consequential-tool prompt: approve/reject, disabled once decided. */
export function ApprovalCard({ approval, locked, onRespond }: Props) {
  const pending = approval.status === "pending";
  return (
    <div className={`approval-card approval-card--${approval.status}`} role="group" aria-label={`approval: ${approval.tool}`}>
      <div className="approval-head">
        <span className="approval-glyph" aria-hidden="true">
          {pending ? "?" : approval.status === "approved" ? "✓" : "✗"}
        </span>
        <span className="approval-tool">{approval.tool}</span>
        <span className="approval-state">{approval.status}</span>
      </div>
      {approval.reason && <p className="approval-reason">{approval.reason}</p>}
      <pre className="approval-args">
        <code>{JSON.stringify(approval.args, null, 2)}</code>
      </pre>
      {pending ? (
        <div className="approval-actions">
          <button type="button" className="btn btn-approve" disabled={locked} onClick={() => onRespond(approval.id, true)}>
            approve
          </button>
          <button type="button" className="btn btn-reject" disabled={locked} onClick={() => onRespond(approval.id, false)}>
            reject
          </button>
        </div>
      ) : (
        <p className="approval-outcome">
          {approval.status === "approved" ? "approved — executed" : "rejected — skipped"}
          {approval.note ? ` · ${approval.note}` : ""}
        </p>
      )}
    </div>
  );
}
