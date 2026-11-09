export interface PageIndexItem {
  id: string;
  label: string;
}

/** Shared section index for multi-section content pages: the `index` label
 * sits on its own line, then one `/section` link per line. */
export function PageIndex({ items }: { items: readonly PageIndexItem[] }) {
  return (
    <nav className="page-index" aria-label="On this page">
      <span className="page-index-label">index</span>
      <span className="page-index-links">
        {items.map((item) => (
          <a key={item.id} href={`#${item.id}`}>
            <span className="page-index-slash" aria-hidden="true">
              /
            </span>
            {item.id}
          </a>
        ))}
      </span>
    </nav>
  );
}
