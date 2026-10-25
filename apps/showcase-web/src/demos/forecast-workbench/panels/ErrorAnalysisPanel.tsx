import { useMeasuredSize } from "../../charts/useMeasuredSize";
import type { ModelKey, OriginBlock } from "../../types";
import { latticeErrors } from "../kpis";
import { MODEL_COLOR } from "./ExplorerPanel";
import { Figure } from "./common";

const C_OVER = "#f472b6";
const C_UNDER = "#2dd4bf";
const C_WHITE = "#f8fafc";

/** Error Analysis: the signed error of every direct h-step forecast at this
 * origin (over pink / under teal), the worst day annotated, click-a-day →
 * highlights that day on the explorer canvas. */
export function ErrorAnalysisPanel({
  origin,
  model,
  shock,
  highlightDay,
  onHighlight,
}: {
  origin: OriginBlock | null;
  model: ModelKey;
  shock: number;
  highlightDay: number | null;
  onHighlight: (h: number | null) => void;
}) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 480;
  const H = size?.h ?? 140;
  const errs = latticeErrors(origin, model, shock);
  const max = Math.max(...errs.map((e) => e.abs), 1);
  const pad = 12;
  const labelH = 14;
  const plotH = (H - pad * 2 - labelH) / 2;
  const zeroY = pad + plotH;
  const groupW = (W - pad * 2) / Math.max(1, errs.length);
  const barW = Math.max(3, groupW * 0.5);
  const worst = errs.reduce((a, b) => (b.abs > a.abs ? b : a), errs[0] ?? null);
  const overN = errs.filter((e) => e.over).length;
  const meanAbs = errs.length ? errs.reduce((a, e) => a + e.abs, 0) / errs.length : 0;

  return (
    <Figure
      comment={
        <>
          Signed error per direct h-step forecast for the{" "}
          <strong style={{ color: MODEL_COLOR[model] }}>{model}</strong> curve — over pink, under
          teal. Click a bar to pin that day on the explorer.
        </>
      }
    >
      <div ref={ref} className="wb-panel-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`signed direct-horizon ${model} forecast errors, colored by sign`}
        >
          <line x1={pad} x2={W - pad} y1={zeroY} y2={zeroY} stroke="var(--border)" />
          {errs.map((e) => {
            const x0 = pad + errs.indexOf(e) * groupW;
            const bh = (e.abs / max) * (plotH - 6);
            const y = e.over ? zeroY - bh : zeroY;
            const active = highlightDay === e.h;
            return (
              <g key={e.h}>
                <rect
                  x={x0 + (groupW - barW) / 2}
                  y={y}
                  width={barW}
                  height={Math.max(bh, e.abs > 0 ? 1.5 : 0)}
                  fill={e.over ? C_OVER : C_UNDER}
                  opacity={active ? 1 : 0.8}
                  stroke={active ? C_WHITE : "none"}
                  strokeWidth={active ? 1.5 : 0}
                  style={{ cursor: "pointer" }}
                  onClick={() => onHighlight(active ? null : e.h)}
                >
                  <title>
                    h={e.h} · {e.signed >= 0 ? "+" : ""}
                    {e.signed.toFixed(2)} units ({e.over ? "over" : "under"}) · {e.date}
                  </title>
                </rect>
                <text x={x0 + groupW / 2} y={H - 2} textAnchor="middle" className="demo-axis-label">
                  h{e.h}
                </text>
                <text
                  x={x0 + groupW / 2}
                  y={e.over ? y - 3 : y + bh + 9}
                  textAnchor="middle"
                  className="demo-axis-label"
                >
                  {e.signed >= 0 ? "+" : ""}
                  {e.signed.toFixed(1)}
                </text>
                {worst && e.h === worst.h && e.abs > 0 && (
                  <circle
                    cx={x0 + groupW / 2}
                    cy={e.over ? Math.max(8, y - 12) : y + bh + 16}
                    r={2.5}
                    fill={C_WHITE}
                  >
                    <title>
                      worst day: h={e.h} · {e.signed >= 0 ? "+" : ""}
                      {e.signed.toFixed(2)} units ({e.over ? "over" : "under"}) · {e.date}
                    </title>
                  </circle>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="demo-hint">
        <span className="wb-legend-swatch" style={{ background: C_OVER }} /> over{" "}
        <span className="wb-legend-swatch" style={{ background: C_UNDER }} /> under — over on{" "}
        <strong>
          {overN} of {errs.length}
        </strong>{" "}
        horizons ({errs.length ? Math.round((overN / errs.length) * 100) : 0}%) · mean |err|{" "}
        <strong>{meanAbs.toFixed(1)}</strong> units
        {worst && worst.abs > 0 && (
          <>
            {" "}
            · worst <strong>h={worst.h}</strong> ({worst.abs.toFixed(1)} units{" "}
            {worst.over ? "over" : "under"}, {worst.date})
          </>
        )}
      </p>
    </Figure>
  );
}
