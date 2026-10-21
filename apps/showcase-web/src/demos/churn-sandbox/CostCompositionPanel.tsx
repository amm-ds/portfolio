import type { ConfusionRow } from "../types";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import { fnCostSeries, fpCostSeries } from "./kpis";

const C_FP = "#fbbf24";
const C_FN = "#f472b6";
const C_CURSOR = "#f472b6";

/**
 * Why the main cost curve has its shape: the two stacked components of total
 * cost across the threshold grid at the current miss multiplier — FP cost
 * (amber) on the bottom, FN cost (pink) stacked on top — with a vertical
 * marker at the cursor threshold. Rescales live with the FN slider and
 * follows the cursor.
 */
export function CostCompositionPanel({
  overall,
  thresholds,
  fnRatio,
  cursorIdx,
}: {
  overall: ConfusionRow[];
  thresholds: number[];
  fnRatio: number;
  cursorIdx: number;
}) {
  // The panel fills its grid cell; measure the container so the viewBox aspect
  // matches the box — a fixed viewBox + preserveAspectRatio would letterbox
  // the stacked areas inside the wide, short secondary panel.
  const { ref: wrapRef, size: measured } = useMeasuredSize<HTMLDivElement>();
  const W = measured?.w ?? 380;
  const H = measured?.h ?? 120;
  const pad = { l: 38, r: 8, t: 8, b: 20 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;

  const fp = fpCostSeries(overall);
  const fn = fnCostSeries(overall, fnRatio);
  const xMin = thresholds[0];
  const xMax = thresholds[thresholds.length - 1];
  const yMax = Math.max(...fp.map((v, i) => v + fn[i]), 1) * 1.05;

  const px = (t: number) => pad.l + ((t - xMin) / (xMax - xMin)) * plotW;
  const py = (c: number) => pad.t + plotH - (c / yMax) * plotH;
  const base = pad.t + plotH;

  const fpTop = thresholds.map((t, i) => `${px(t).toFixed(1)},${py(fp[i]).toFixed(1)}`);
  const totalTop = thresholds.map((t, i) => `${px(t).toFixed(1)},${py(fp[i] + fn[i]).toFixed(1)}`);
  const fpArea = `M${fpTop.join(" L")} L${px(xMax).toFixed(1)},${base} L${px(xMin).toFixed(1)},${base} Z`;
  const fnArea = `M${totalTop.join(" L")} L${fpTop.slice().reverse().join(" L")} Z`;

  const yTicks = [0, yMax / 2, yMax];
  const xTicks = [xMin, (xMin + xMax) / 2, xMax];
  const cursorX = px(thresholds[cursorIdx]);

  return (
    <div className="figure-card">
      <div className="demo-chart cost-composition" ref={wrapRef}>
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="cost composition over alarm threshold"
        >
          {/* grid + axes */}
          {yTicks.map((c) => (
            <g key={`y-${c}`}>
              <line
                x1={pad.l}
                y1={py(c)}
                x2={W - pad.r}
                y2={py(c)}
                stroke="var(--border)"
                strokeOpacity={c === 0 ? 1 : 0.4}
              />
              <text x={pad.l - 6} y={py(c) + 3} textAnchor="end" className="demo-axis-label">
                {Math.round(c)}
              </text>
            </g>
          ))}
          <line x1={pad.l} y1={base} x2={W - pad.r} y2={base} stroke="var(--border)" />
          {xTicks.map((t) => (
            <text key={`x-${t}`} x={px(t)} y={H - 6} textAnchor="middle" className="demo-axis-label">
              {t.toFixed(2)}
            </text>
          ))}

          {/* stacked components: FP (amber) on the bottom, FN (pink) on top */}
          <path data-layer="fp" d={fpArea} fill={C_FP} fillOpacity={0.55} stroke="none" />
          <path data-layer="fn" d={fnArea} fill={C_FN} fillOpacity={0.55} stroke="none" />

          {/* cursor threshold marker */}
          <line
            data-layer="cursor"
            x1={cursorX}
            y1={pad.t}
            x2={cursorX}
            y2={base}
            stroke={C_CURSOR}
            strokeWidth={1.5}
          />
        </svg>
      </div>
      <footer className="figure-card-band">
        <p className="figure-comment">
          FN cost (pink) dominates at low thresholds, FP cost (amber) at high — the minimum is
          where they cross.
        </p>
      </footer>
    </div>
  );
}
