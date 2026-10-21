export interface SliceRow {
  label: string;
  value: number;
  unit?: string;
}

/** Vertical mini bar list (alarm burden by slice) with max-normalized bars. */
export function MiniBars({
  rows,
  ariaLabel,
  color = "var(--accent)",
}: {
  rows: SliceRow[];
  ariaLabel: string;
  color?: string;
}) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="demo-slice-list" aria-label={ariaLabel}>
      {rows.map((r) => (
        <li key={r.label}>
          <span className="demo-slice-label">{r.label}</span>
          <span className="demo-slice-bar">
            <span style={{ width: `${(r.value / max) * 100}%`, background: color }} />
          </span>
          <span className="demo-slice-count">
            {r.value}
            {r.unit ? ` ${r.unit}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
