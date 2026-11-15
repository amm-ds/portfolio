import type { Dataset } from "../api/types";

export function DatasetRegistry({
  datasets,
  selectedId,
  loading,
  onSelect,
}: {
  datasets: Dataset[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="registry" aria-label="Dataset registry">
      <div className="registry__heading">
        <div><span className="eyebrow">registry</span><h2>Datasets</h2></div>
        <span className="count-chip">{datasets.length}</span>
      </div>
      <p className="registry__intro">Pinned inputs and expected outputs. Select a version to inspect its runs.</p>
      <div className="registry__list">
        {loading ? <p className="loading-copy" role="status">Loading datasets…</p> : null}
        {!loading && datasets.length === 0 ? <p className="loading-copy">No datasets registered.</p> : null}
        <ul>
          {datasets.map((dataset) => (
            <li key={dataset.id}>
              <button
                type="button"
                className={`dataset-card ${selectedId === dataset.id ? "is-selected" : ""}`}
                aria-pressed={selectedId === dataset.id}
                onClick={() => onSelect(dataset.id)}
              >
                <span className="dataset-card__topline"><strong>{dataset.name}</strong><code>{dataset.version}</code></span>
                <span>{dataset.description}</span>
                <span className="dataset-card__meta">{dataset.case_count} cases · {dataset.tags.join(" / ")}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="registry__note">
        <span className="eyebrow">comparison rule</span>
        <p>Only runs from the same dataset version appear together. Quality scores range from 0 to 1.</p>
      </div>
    </aside>
  );
}
