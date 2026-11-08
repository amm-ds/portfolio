import type { PageAnalysis } from "../api/types";
import type { SelectedCitation } from "../workbench/useWorkbench";
import { EvidenceChips } from "./EvidenceChips";

export function PageSummaryMode({
  page,
  onReveal,
}: {
  page: PageAnalysis;
  onReveal: (citation: SelectedCitation) => void;
}) {
  const hasSummary = page.summary.summary.trim().length > 0 || page.summary.key_points.length > 0;
  if (!hasSummary) {
    return <p className="muted mode-empty">The analyzer produced no summary text for this page.</p>;
  }
  return (
    <div className="mode-stack">
      {page.summary.summary ? <p className="page-summary-text">{page.summary.summary}</p> : null}
      {page.summary.key_points.length > 0 ? (
        <ol className="key-point-list" aria-label="Key points">
          {page.summary.key_points.map((point, index) => (
            <li key={`${index}-${point.text}`} className="key-point">
              <p>{point.text}</p>
              <EvidenceChips evidence={point.evidence} label={`Key point ${index + 1}`} onReveal={onReveal} />
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
