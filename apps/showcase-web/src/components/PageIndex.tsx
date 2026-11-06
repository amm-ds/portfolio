export interface PageIndexItem {
  id: string;
  label: string;
}

/** Shared section index for multi-section content pages. */
export function PageIndex({ items }: { items: readonly PageIndexItem[] }) {
  return (
    <nav className="page-index" aria-label="On this page">
      <span className="page-index-label">index</span>
      {items.map((item) => (
        <a key={item.id} href={`#${item.id}`}>
          {item.label}
        </a>
      ))}
    </nav>
  );
}
