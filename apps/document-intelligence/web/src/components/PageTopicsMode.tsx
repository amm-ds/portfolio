import type { PageAnalysis } from "../api/types";
import type { SelectedCitation } from "../workbench/useWorkbench";
import { EvidenceChips } from "./EvidenceChips";

export function PageTopicsMode({
  page,
  onReveal,
}: {
  page: PageAnalysis;
  onReveal: (citation: SelectedCitation) => void;
}) {
  if (page.topics.length === 0) {
    return <p className="muted mode-empty">No topics were identified on this page.</p>;
  }
  return (
    <ul className="topic-card-list">
      {page.topics.map((topic, index) => (
        <li key={`${index}-${topic.label}`} className="topic-card">
          <h3>{topic.label}</h3>
          <div className="analysis-rationale">
            <span>Rationale</span>
            <p>{topic.rationale}</p>
          </div>
          <EvidenceChips evidence={topic.evidence} label={`Topic ${topic.label}`} onReveal={onReveal} />
        </li>
      ))}
    </ul>
  );
}
