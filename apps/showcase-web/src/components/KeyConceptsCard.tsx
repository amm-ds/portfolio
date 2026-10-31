import { renderMarkdown } from "../lib/markdown";

/**
 * The story's authored key concepts: each item is a `**Term** — sentence`
 * markdown line. Rendered in the case study right before the GlossaryCard
 * (after the Background section); renders nothing when the story carries no
 * concepts.
 */
export function KeyConceptsCard({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <aside className="glossary-card key-concepts-card" aria-label="Key concepts">
      <div className="glossary-card-head">
        <span className="glossary-card-label">key concepts</span>
      </div>
      <ul className="key-concepts-list">
        {items.map((item, i) => (
          <li key={i}>{renderMarkdown(item)}</li>
        ))}
      </ul>
    </aside>
  );
}
