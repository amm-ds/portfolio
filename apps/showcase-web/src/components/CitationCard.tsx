import type { Citation } from "../api";

/** One retrieved source: title, excerpt, relevance score bar. */
export function CitationCard({ citation }: { citation: Citation }) {
  const pct = Math.round(Math.max(0, Math.min(1, citation.score)) * 100);
  return (
    <div className="citation-card">
      <p className="citation-title">{citation.title}</p>
      <p className="citation-excerpt">{citation.excerpt}</p>
      <div className="score-bar" aria-label={`score ${citation.score.toFixed(2)}`}>
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="score-label">relevance {citation.score.toFixed(2)}</p>
    </div>
  );
}
