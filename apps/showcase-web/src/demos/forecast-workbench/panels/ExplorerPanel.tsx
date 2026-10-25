import { useMemo } from "react";
import { LineChart, type LineMarker } from "../../charts/LineChart";
import { useMeasuredSize } from "../../charts/useMeasuredSize";
import type { CatalogSeries, ModelKey, OriginBlock } from "../../types";
import { curveAt, fmtDay, modelBlock, plottedPath, windowAxis } from "../kpis";
import { Figure } from "./common";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_WHITE = "#f8fafc";

export const MODEL_COLOR: Record<ModelKey, string> = {
  zero: "#64748b",
  routed: C_TEAL,
  champion: C_PINK,
  hurdle: C_AMBER,
  tweedie: "#a78bfa",
};

/** The drawn axis + its date→index map (see `windowAxis` in ../kpis — the
 * axis must be wall-calendar contiguous even across DST transitions). */
function useAxis(origin: OriginBlock | null): { axis: string[]; idx: Map<string, number> } {
  return useMemo(() => {
    const axis = windowAxis(origin);
    return { axis, idx: new Map(axis.map((d, i) => [d, i])) };
  }, [origin]);
}

/** The as-of-origin canvas: history left of the marker (ends the day before
 * it), the selected model's DIRECT h-step forecasts as a contiguous 14-day
 * curve starting the day after (one real direct-h model per window day on
 * the committed full h = 1..14 lattice — no gaps, no interpolation), the
 * window's actuals as a ghost overlay — and nothing shaded, because there is
 * no embargo gap: the window abuts the origin. */
export function ExplorerPanel({
  series,
  origin,
  model,
  horizon,
  shock,
  highlightDay,
}: {
  series: CatalogSeries;
  origin: OriginBlock | null;
  model: ModelKey;
  horizon: number;
  shock: number;
  highlightDay: number | null;
}) {
  const blk = origin;
  const hist = blk?.history ?? { dates: [], y: [] };
  const actuals = blk?.actuals ?? { dates: [], y: [] };
  const block = modelBlock(blk, model);
  const pred = curveAt(block, shock);
  const { axis, idx } = useAxis(blk ?? null);
  const total = axis.length;

  const nan = (k: number) => Array<number>(Math.max(0, k)).fill(NaN);
  const at = (dates: string[], vals: number[], n: number): number[] => {
    const out = nan(n);
    for (let i = 0; i < dates.length; i++) {
      const j = idx.get(dates[i]);
      if (j !== undefined) out[j] = vals[i];
    }
    return out;
  };
  const histVals = at(hist.dates, hist.y, total);
  const actualVals = at(actuals.dates, actuals.y, total);

  // direct curve: one point per direct h at day origin+h — the full 1..14
  // lattice, so the drawn path covers the whole window contiguously
  const predVals = nan(total);
  const p10Vals = nan(total);
  const p90Vals = nan(total);
  const ladderLines: Array<{ level: string; y: number }> = [];
  if (blk && block) {
    for (const { date, y } of plottedPath(blk, model, shock)) {
      const j = idx.get(date);
      if (j !== undefined) predVals[j] = y;
    }
    blk.horizons.forEach((h, i) => {
      const j = idx.get(actuals.dates[h - 1]);
      if (j === undefined) return;
      if (block.p10 && block.p90) {
        p10Vals[j] = block.p10[i];
        p90Vals[j] = block.p90[i];
      }
    });
    if (block.band) {
      for (const [level, y] of Object.entries(block.band.ladder)) {
        ladderLines.push({ level, y });
      }
    }
  }

  const originIdx = blk ? idx.get(blk.origin_date) : undefined;
  const cMax = Math.max(
    ...hist.y,
    ...pred.filter((v) => Number.isFinite(v)),
    ...actuals.y,
    ...(block?.p90 ?? []),
    ...ladderLines.map((l) => l.y),
    1,
  ) * 1.08;

  const markers: LineMarker[] = [];
  if (originIdx !== undefined && blk) {
    markers.push({
      xIndex: originIdx,
      label: `forecast origin · ${fmtDay(blk.origin_date)}`,
      style: "dashed",
    });
  }
  if (highlightDay !== null && blk) {
    const j = idx.get(actuals.dates[highlightDay - 1]);
    if (j !== undefined) {
      markers.push({
        xIndex: j,
        label: `h=${highlightDay}`,
        style: "solid",
        color: C_PINK,
        top: false,
      });
    }
  }

  // band polygon + ladder reference lines on an overlay SVG sharing the chart's
  // padding/scale math
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const pad = { l: 52, r: 18, t: 16, b: 32 };
  const W = size?.w ?? 720;
  const Hpx = size?.h ?? 280;
  const plotW = W - pad.l - pad.r;
  const plotH = Hpx - pad.t - pad.b;
  const px = (i: number) => pad.l + (i / Math.max(1, total - 1)) * plotW;
  const py = (v: number) => pad.t + plotH - (v / cMax) * plotH;

  let bandPath: string | null = null;
  const bandPts = p90Vals
    .map((v, i) => (Number.isFinite(v) && Number.isFinite(p10Vals[i]) ? { i, lo: p10Vals[i], hi: v } : null))
    .filter((p): p is { i: number; lo: number; hi: number } => p !== null);
  if (bandPts.length > 1) {
    const fwd = bandPts.map((p) => `${px(p.i).toFixed(1)},${py(p.hi).toFixed(1)}`);
    const back = [...bandPts].reverse().map((p) => `${px(p.i).toFixed(1)},${py(p.lo).toFixed(1)}`);
    bandPath = `M${fwd.join(" L")} L${back.join(" L")} Z`;
  }

  return (
    <Figure
      comment={
        <>
          Issued <strong>{fmtDay(blk?.origin_date ?? "")}</strong> — direct h-step forecasts;
          everything right of the marker was unknown then. The history ends the day before the
          origin and the fan starts the day after it: the window abuts the origin, so there is no
          gap to shade. The curve is a historical backtest against the frozen window, not a live
          prediction.
          {block?.band
            ? ` Sparse band: P(sale) ${(block.band.p_sale * 100).toFixed(0)}% + the training-history quantile ladder (amber lines) — an honest band that cannot collapse to zero width.`
            : block?.p10 && block?.p90
              ? " The teal fan is the committed per-h split-conformal p10–p90 band."
              : ""}
        </>
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">{series.label}</span>
        <span className="chip demo-readout">{series.demand_class}</span>
        <span className="chip demo-readout">origin {fmtDay(blk?.origin_date ?? "")}</span>
        <span className="chip demo-readout">h = {horizon}</span>
        <span className="chip demo-readout">{model}</span>
        {shock !== 1 && <span className="chip demo-readout">shock ×{shock.toFixed(1)}</span>}
        {highlightDay !== null && (
          <span className="chip demo-readout" style={{ color: C_PINK }}>
            error day h={highlightDay}
          </span>
        )}
      </div>
      <div className="demo-chart">
        <div ref={ref} className="wb-fan">
          <LineChart
            x={Array.from({ length: total }, (_, i) => i)}
            series={[
              { name: "history", color: C_WHITE, values: histVals },
              {
                name: model,
                color: MODEL_COLOR[model],
                dashed: true,
                values: predVals,
              },
              { name: "actuals", color: C_WHITE, dashed: true, values: actualVals },
            ]}
            yMax={cMax}
            pad={pad}
            markers={markers}
            xTicks={6}
            formatX={(i) => fmtDay(axis[Math.round(i)] ?? "")}
            ariaLabel="as-of-origin demand history with direct h-step forecast fan and ghost actuals"
          />
          <svg
            className="wb-fan-band"
            width="100%"
            height="100%"
            viewBox={`0 0 ${W} ${Hpx}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {bandPath && <path d={bandPath} fill={C_TEAL} fillOpacity={0.15} />}
            {ladderLines.map((l) => (
              <g key={l.level}>
                <line
                  x1={pad.l}
                  x2={W - pad.r}
                  y1={py(l.y)}
                  y2={py(l.y)}
                  stroke={C_AMBER}
                  strokeDasharray="3 5"
                  strokeOpacity={0.5}
                />
                <text
                  x={W - pad.r - 2}
                  y={py(l.y) - 2}
                  textAnchor="end"
                  className="demo-axis-label"
                >
                  q{l.level}
                </text>
              </g>
            ))}
          </svg>
        </div>
      </div>
      <p className="demo-hint">
        history solid white · {model} fan dashed teal/pink (one point per direct h) · actuals ghost
        dashed · amber lines: the sparse quantile ladder
      </p>
    </Figure>
  );
}
