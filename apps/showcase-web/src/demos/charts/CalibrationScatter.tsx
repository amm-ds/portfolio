export interface CalibrationPoint {
  x: number;
  y: number;
  n: number;
}

/** Predicted-vs-observed calibration scatter with the diagonal and n-scaled markers. */
export function CalibrationScatter({
  points,
  width = 340,
  height = 260,
  pad = { l: 40, r: 14, t: 14, b: 34 },
  color = "#2dd4bf",
  ariaLabel = "calibration scatter",
}: {
  points: CalibrationPoint[];
  width?: number;
  height?: number;
  pad?: { l: number; r: number; t: number; b: number };
  color?: string;
  ariaLabel?: string;
}) {
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const cx = (v: number) => pad.l + v * plotW;
  const cy = (v: number) => pad.t + plotH - v * plotH;
  const maxN = Math.max(...points.map((p) => p.n), 1);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
      <line x1={cx(0)} y1={cy(0)} x2={cx(1)} y2={cy(0)} stroke="var(--border)" />
      <line x1={cx(0)} y1={cy(0)} x2={cx(0)} y2={cy(1)} stroke="var(--border)" />
      <line x1={cx(0)} y1={cy(0)} x2={cx(1)} y2={cy(1)} stroke="var(--muted)" strokeDasharray="4 4" />
      <text x={cx(1)} y={cy(0) + 16} textAnchor="end" className="demo-axis-label">
        predicted
      </text>
      <text x={cx(0) + 4} y={cy(1) + 12} className="demo-axis-label">
        observed
      </text>
      {points.map((p) => (
        <circle
          key={p.x}
          cx={cx(p.x)}
          cy={cy(p.y)}
          r={3 + 9 * Math.sqrt(p.n / maxN)}
          fill={color}
          fillOpacity={0.75}
        >
          <title>
            p̂ {p.x.toFixed(2)} → {p.y.toFixed(2)} (n = {p.n})
          </title>
        </circle>
      ))}
    </svg>
  );
}
