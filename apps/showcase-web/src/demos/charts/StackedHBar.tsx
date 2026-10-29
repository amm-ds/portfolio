export interface HBarSegment {
  label: string;
  value: number;
  color: string;
}

/** Legend for color-keyed segments. */
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
