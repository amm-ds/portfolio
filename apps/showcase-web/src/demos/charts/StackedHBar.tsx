export interface HBarSegment {
  label: string;
  value: number;
  color: string;
}

/** Single horizontal stacked bar (outcome mix), normalized to the segment total. */
export function StackedHBar({
  segments,
  ariaLabel,
}: {
  segments: HBarSegment[];
  ariaLabel: string;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <div className="demo-stack-bar" role="img" aria-label={ariaLabel}>
      {segments.map((s) =>
        s.value > 0 ? (
          <span
            key={s.label}
            style={{ width: `${(s.value / total) * 100}%`, background: s.color }}
            title={`${s.label}: ${s.value}`}
          />
        ) : null,
      )}
    </div>
  );
}

/** Legend for a StackedHBar (or any color-keyed segments). */
export function SegmentLegend({ segments }: { segments: HBarSegment[] }) {
  return (
    <ul className="demo-outcome-legend">
      {segments.map((s) => (
        <li key={s.label}>
          <span className="demo-swatch" style={{ background: s.color }} />
          <span className="demo-outcome-count">
            {s.label} {s.value}
          </span>
        </li>
      ))}
    </ul>
  );
}
