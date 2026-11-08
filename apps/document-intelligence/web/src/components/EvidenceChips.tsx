import type { Evidence } from "../api/types";
import type { SelectedCitation } from "../workbench/useWorkbench";

/**
 * Read-only citation chips. Clicking reveals the source in the PDF viewer;
 * unresolved evidence is shown honestly and cannot be highlighted.
 */
export function EvidenceChips({
  evidence,
  label,
  onReveal,
}: {
  evidence: Evidence[];
  label: string;
  onReveal: (citation: SelectedCitation) => void;
}) {
  if (evidence.length === 0) return <p className="citation-empty">No source citations supplied.</p>;
  return (
    <ul className="citation-chips" aria-label={`${label} citations`}>
      {evidence.map((item, index) => {
        const citationLabel = `${label} citation ${index + 1}`;
        const canReveal = item.resolved && item.page !== null;
        return (
          <li key={`${index}-${item.quote}`} className="citation-chip" data-resolved={item.resolved}>
            <blockquote>“{item.quote}”</blockquote>
            <div className="citation-chip__meta">
              <span>
                {item.page !== null ? `Page ${item.page}` : "Page unavailable"} ·{" "}
                {item.resolved ? "resolved" : "unresolved"}
              </span>
              <button
                type="button"
                className="button button--small"
                disabled={!canReveal}
                title={canReveal ? "Reveal the quote in the original PDF" : "The backend could not resolve this quote"}
                aria-label={`Reveal source for ${citationLabel}`}
                onClick={() => onReveal({ label: citationLabel, evidence: item })}
              >
                Reveal source
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
