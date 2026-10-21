import { useEffect, useRef, useState } from "react";

export interface LineSeries {
  name: string;
  color: string;
  dashed?: boolean;
  values: number[];
}

export interface LineMarker {
  xIndex: number;
  label?: string;
  /** "solid" | "dashed" | "star" — star renders a ★ at the series point. */
  style: "solid" | "dashed" | "star";
  color?: string;
  top?: boolean;
}

export interface BandFill {
  /** Fill the vertical slice between series[a] and series[b] (by index). */
  between: [number, number];
  color: string;
  opacity?: number;
}

/** Format an axis tick; defaults to integers. */
export type TickFormat = (value: number) => string;

const C_CURSOR = "#f472b6";

/**
 * Generic multi-series SVG line chart on a numeric x domain (typically a
 * threshold grid). Supports an optional draggable cursor (pointer events
 * clamped to the plot grid), vertical marker lines, and an area fill between
 * two series for CI-style bands. Sizing is viewBox-based; the SVG stretches
 * to its container.
 */
export function LineChart({
  width: widthProp = 720,
  height: heightProp = 280,
  pad = { l: 52, r: 18, t: 16, b: 32 },
  x,
  series,
  yMax,
  cursor,
  onCursorChange,
  markers = [],
  band,
  yTicks = 2,
  xTicks = 3,
  formatX,
  formatY,
  ariaLabel,
  children,
}: {
  width?: number;
  height?: number;
  pad?: { l: number; r: number; t: number; b: number };
  /** X values, strictly increasing; index-addressed like the series values. */
  x: number[];
  series: LineSeries[];
  /** Y ceiling; defaults to max(series) × 1.08. */
  yMax?: number;
  /** Cursor index into x/series; enables the draggable cursor. */
  cursor?: number;
  onCursorChange?: (xIndex: number) => void;
  markers?: LineMarker[];
  band?: BandFill;
  yTicks?: number;
  xTicks?: number;
  formatX?: TickFormat;
  formatY?: TickFormat;
  ariaLabel: string;
  children?: React.ReactNode;
}) {
  const fmtX = formatX ?? ((v: number) => v.toFixed(2));
  const fmtY = formatY ?? ((v: number) => String(Math.round(v)));
  const wrapRef = useRef<HTMLDivElement | null>(null);
  // The chart fills its grid cell; measure the container so the viewBox aspect
  // matches the box — otherwise preserveAspectRatio letterboxes the curve
  // (fixed 720x280 viewBox in a wide, short cell renders tiny).
  const [measured, setMeasured] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r && r.width > 0 && r.height > 0) {
        setMeasured({ w: Math.round(r.width), h: Math.round(r.height) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const width = measured?.w ?? widthProp;
  const height = measured?.h ?? heightProp;
  const svgRef = useRef<SVGSVGElement | null>(null);

  const xMin = x[0];
  const xMax = x[x.length - 1];
  const computedMax = Math.max(...series.flatMap((s) => s.values), 1) * 1.08;
  const cMax = yMax ?? computedMax;
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const px = (t: number) => pad.l + ((t - xMin) / (xMax - xMin)) * plotW;
  const py = (c: number) => pad.t + plotH - (c / cMax) * plotH;

  // pointer position → nearest x index (viewBox-aware for CSS scaling)
  const pick = (clientX: number) => {
    const el = svgRef.current;
    if (!el || !onCursorChange) return;
    const rect = el.getBoundingClientRect();
    const vx = ((clientX - rect.left) / rect.width) * width;
    const frac = (vx - pad.l) / plotW;
    const t = xMin + Math.min(1, Math.max(0, frac)) * (xMax - xMin);
    let best = 0;
    for (let i = 1; i < x.length; i++) {
      if (Math.abs(x[i] - t) < Math.abs(x[best] - t)) best = i;
    }
    onCursorChange(best);
  };

  const xTickValues = Array.from(
    { length: xTicks },
    (_, i) => xMin + ((xMax - xMin) * i) / Math.max(1, xTicks - 1),
  );
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => (cMax * i) / yTicks);

  const cursorX = cursor !== undefined ? x[cursor] : undefined;

  // band polygon: series[a] left-to-right, then series[b] right-to-left
  let bandPath: string | null = null;
  if (band) {
    const [ai, bi] = band.between;
    const a = series[ai];
    const b = series[bi];
    if (a && b) {
      const fwd = x.map((t, i) => `${px(t).toFixed(1)},${py(a.values[i]).toFixed(1)}`);
      const back = x
        .map((t, i) => `${px(t).toFixed(1)},${py(b.values[i]).toFixed(1)}`)
        .reverse();
      bandPath = `M${fwd.join(" L")} L${back.join(" L")} Z`;
    }
  }

  const draggable = cursor !== undefined && onCursorChange !== undefined;

  return (
    <div ref={wrapRef} style={{ width: "100%", height: "100%", minHeight: 0 }}>
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
      aria-label={ariaLabel}
      onPointerDown={(e) => {
        if (!draggable) return;
        pick(e.clientX);
        if (e.pointerId !== undefined) {
          try {
            e.currentTarget.setPointerCapture?.(e.pointerId);
          } catch {
            // jsdom / older browsers: drag still works via pointermove buttons
          }
        }
      }}
      onPointerMove={(e) => {
        if (draggable && e.buttons > 0) pick(e.clientX);
      }}
    >
      {/* axes */}
      <line x1={pad.l} y1={height - pad.b} x2={width - pad.r} y2={height - pad.b} stroke="var(--border)" />
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={height - pad.b} stroke="var(--border)" />
      {xTickValues.map((t) => (
        <g key={`x-${t}`}>
          <line x1={px(t)} y1={height - pad.b} x2={px(t)} y2={height - pad.b + 4} stroke="var(--border)" />
          <text x={px(t)} y={height - pad.b + 16} textAnchor="middle" className="demo-axis-label">
            {fmtX(t)}
          </text>
        </g>
      ))}
      {yTickValues.map((c) => (
        <text
          key={`y-${c}`}
          x={pad.l - 8}
          y={py(c)}
          textAnchor="end"
          className="demo-axis-label"
        >
          {fmtY(c)}
        </text>
      ))}

      {bandPath && (
        <path d={bandPath} fill={band!.color} fillOpacity={band!.opacity ?? 0.15} stroke="none" />
      )}

      {series.map((s) => (
        <polyline
          key={s.name}
          points={x.map((t, i) => `${px(t).toFixed(1)},${py(s.values[i]).toFixed(1)}`).join(" ")}
          fill="none"
          stroke={s.color}
          strokeWidth={2}
          strokeDasharray={s.dashed ? "4 4" : undefined}
        />
      ))}

      {markers.map((m, i) => {
        const mx = x[m.xIndex];
        if (m.style === "star") {
          const s = series[0];
          return (
            <text
              key={i}
              x={px(mx)}
              y={py(s.values[m.xIndex]) - 10}
              textAnchor="middle"
              className="demo-star"
            >
              ★
            </text>
          );
        }
        const dashed = m.style === "dashed";
        return (
          <g key={i}>
            <line
              x1={px(mx)}
              y1={pad.t}
              x2={px(mx)}
              y2={height - pad.b}
              stroke={m.color ?? "var(--muted)"}
              strokeDasharray={dashed ? "4 4" : undefined}
            />
            {m.label && (
              <text
                x={px(mx) + 4}
                y={m.top === false ? height - pad.b - 6 : pad.t + 10}
                className="demo-axis-label"
              >
                {m.label}
              </text>
            )}
          </g>
        );
      })}

      {draggable && cursor !== undefined && cursorX !== undefined && (
        <g>
          <line
            x1={px(cursorX)}
            y1={pad.t}
            x2={px(cursorX)}
            y2={height - pad.b}
            stroke={C_CURSOR}
            strokeWidth={1.5}
          />
          <circle cx={px(cursorX)} cy={py(series[0].values[cursor])} r={5} fill={C_CURSOR} />
        </g>
      )}

      {children}
      </svg>
    </div>
  );
}
