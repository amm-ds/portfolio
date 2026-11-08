import { useMemo, useState } from "react";
import { ENTITY_TYPES } from "../api/types";
import type { EntityType, PageAnalysis } from "../api/types";
import type { SelectedCitation } from "../workbench/useWorkbench";
import { EvidenceChips } from "./EvidenceChips";

export function PageEntitiesMode({
  page,
  onReveal,
}: {
  page: PageAnalysis;
  onReveal: (citation: SelectedCitation) => void;
}) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | EntityType>("all");

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = page.entities.filter((entity) => {
      if (typeFilter !== "all" && entity.type !== typeFilter) return false;
      if (!needle) return true;
      return entity.name.toLowerCase().includes(needle) || entity.text.toLowerCase().includes(needle);
    });
    return ENTITY_TYPES.map((type) => ({
      type,
      entities: filtered.filter((entity) => entity.type === type),
    })).filter((group) => group.entities.length > 0);
  }, [page.entities, query, typeFilter]);

  if (page.entities.length === 0) {
    return <p className="muted mode-empty">No entities were extracted from this page.</p>;
  }

  return (
    <div>
      <div className="entity-filters">
        <label>
          <span className="sr-only">Search entities</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search text or name…"
            aria-label="Search entities"
          />
        </label>
        <label>
          <span className="sr-only">Filter by type</span>
          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as "all" | EntityType)}
            aria-label="Filter entities by type"
          >
            <option value="all">All types</option>
            {ENTITY_TYPES.map((type) => (
              <option key={type} value={type}>{type.replaceAll("_", " ")}</option>
            ))}
          </select>
        </label>
      </div>
      {groups.length === 0 ? <p className="muted mode-empty">No entities match this filter.</p> : null}
      {groups.map((group) => (
        <section key={group.type} className="entity-group" aria-label={`${group.type} entities`}>
          <h3 className="entity-group__heading">
            <span className="status-badge">{group.type.replaceAll("_", " ")}</span>
            <span className="entity-group__count">{group.entities.length}</span>
          </h3>
          <ul className="entity-card-list">
            {group.entities.map((entity, index) => (
              <li key={`${index}-${entity.text}`} className="entity-card">
                <div className="entity-card__topline">
                  <strong>{entity.name}</strong>
                  <code>{entity.text}</code>
                </div>
                <EvidenceChips evidence={[entity.evidence]} label={`Entity ${entity.name}`} onReveal={onReveal} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
