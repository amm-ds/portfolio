import { Link } from "react-router-dom";
import type { GlossaryEntry } from "../lib/glossary";

/**
 * Per-project glossary card: the terms this case study actually uses, each
 * with its plain definition, in first-use order. Rendered at the end of the
 * Background section — the definitions used to appear as hover popups on
 * linked terms; the owner asked to remove popups entirely and surface the
 * vocabulary here instead. Capped so it stays a reference, not a wall.
 */
export function GlossaryCard({ terms }: { terms: GlossaryEntry[] }) {
  if (terms.length === 0) return null;
  return (
    <aside className="glossary-card" aria-label="Glossary for this case study">
      <div className="glossary-card-head">
        <span className="glossary-card-label">glossary</span>
        <span className="glossary-card-hint">
          terms this case study uses —{" "}
          <Link to="/glossary">full glossary</Link>
        </span>
      </div>
      <dl className="glossary-card-list">
        {terms.map((entry) => (
          <div className="glossary-card-row" key={entry.slug}>
            <dt>
              <Link to={`/glossary#${entry.slug}`}>{entry.term}</Link>
            </dt>
            <dd>{entry.definition}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
