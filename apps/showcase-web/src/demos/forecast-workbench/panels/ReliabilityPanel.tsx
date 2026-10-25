import { useMeasuredSize } from "../../charts/useMeasuredSize";
import type {
  CatalogSeries,
  DecisionBlock,
  ForecastPayload,
  HorizonGrowth,
  OriginBlock,
} from "../../types";
import { curveAt, growthAt, growthMaseAt, orderPolicy, policyWindow } from "../kpis";
import { Figure } from "./common";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";

/** RELIABILITY + DECISION (always visible): committed per-h coverage vs
 * target with the width trend and the calibration verdict, the pooled
 * error-growth spark with the current h marked, and the order-up-to τ strip
 * for the selected series — the τ strip refits on series/origin changes,
 * the h markers on the h slider. */
export function ReliabilityPanel({
  payload,
  series,
  origin,
  horizon,
  tau,
  onTau,
}: {
  payload: ForecastPayload;
  series: CatalogSeries;
  origin: OriginBlock | null;
  /** Current h — marked on the coverage and growth minis. */
  horizon: number;
  /** Service level τ (decision layer) + setter. */
  tau: number;
  onTau: (tau: number) => void;
}) {
  return (
    <Figure
      comment={
        <>
          Committed bands + error growth vs the true horizon — the h-slider is real. Below: the
          order-up-to τ simulation for this series' window.
        </>
      }
    >
      <CoverageWidth payload={payload} horizon={horizon} />
      <GrowthMini growth={payload.horizon_growth} horizon={horizon} />
      <DecisionStrip
        decision={payload.decision}
        series={series}
        origin={origin}
        tau={tau}
        onTau={onTau}
      />
    </Figure>
  );
}

/** Coverage bars per h + target line + width trend; the current h is
 * outlined so the mini responds to the horizon slider. */
function CoverageWidth({ payload, horizon }: { payload: ForecastPayload; horizon: number }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 300;
  const H = size?.h ?? 90;
  const bands = payload.bands;
  const hs = Object.keys(bands.per_horizon).map(Number).sort((a, b) => a - b);
  const pad = 10;
  const labelH = 12;
  const panel = (H - pad * 2 - labelH) / 2;
  const zero2 = pad + panel;
  const groupW = (W - pad * 2) / Math.max(1, hs.length);
  const barW = Math.max(3, groupW * 0.5);
  const widths = hs.map((h) => bands.per_horizon[String(h)].avg_width);
  const maxW = Math.max(...widths, 1);
  const target = bands.target_coverage;

  return (
    <div ref={ref} className="wb-panel-viz" style={{ minHeight: 56, flex: "3 1 0" }}>
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="per-horizon coverage versus target and band width trend"
      >
        {hs.map((h, i) => {
          const c = bands.per_horizon[String(h)].coverage;
          const x0 = pad + i * groupW;
          const bh = Math.min(c, 1) * (panel - 6);
          return (
            <g key={h}>
              <rect
                x={x0 + (groupW - barW) / 2}
                y={pad + panel - 6 - bh}
                width={barW}
                height={Math.max(bh, c > 0 ? 1.5 : 0)}
                fill={C_TEAL}
                opacity={h === horizon ? 1 : 0.7}
                stroke={h === horizon ? C_PINK : "none"}
                strokeWidth={h === horizon ? 1.5 : 0}
              >
                <title>
                  h={h}: {(c * 100).toFixed(1)}% coverage, width{" "}
                  {bands.per_horizon[String(h)].avg_width.toFixed(2)}
                </title>
              </rect>
              <text x={x0 + groupW / 2} y={pad + panel + 8} textAnchor="middle" className="demo-axis-label">
                h{h}
              </text>
            </g>
          );
        })}
        <line
          x1={pad}
          x2={W - pad}
          y1={pad + panel - 6 - target * (panel - 6)}
          y2={pad + panel - 6 - target * (panel - 6)}
          stroke={C_GRAY}
          strokeDasharray="4 4"
        />
        <text x={pad + 2} y={pad + panel - 10 - target * (panel - 6)} className="demo-axis-label">
          target {(target * 100).toFixed(0)}%
        </text>
        <text x={pad + 2} y={zero2 + 11} className="demo-axis-label">
          width
        </text>
        {hs.length > 1 && (
          <polyline
            points={widths
              .map(
                (w, i) =>
                  `${pad + i * groupW + groupW / 2},${zero2 + 14 + (1 - w / maxW) * (panel - 20)}`,
              )
              .join(" ")}
            fill="none"
            stroke={C_AMBER}
            strokeWidth={1.5}
          />
        )}
      </svg>
    </div>
  );
}

/** The pooled error-growth spark (routed vs floor vs zero) with the pooled
 * MASE curves; the current h is marked. */
function GrowthMini({ growth, horizon }: { growth: HorizonGrowth; horizon: number }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 300;
  const H = size?.h ?? 80;
  const hs = growth.horizons;
  const pad = 10;
  const routes: Array<{ name: string; color: string; dash?: string }> = [
    { name: "routed", color: C_TEAL },
    { name: "seasonal_naive", color: C_GRAY, dash: "5 4" },
    { name: "zero", color: C_AMBER, dash: "2 4" },
  ];
  const vals = (name: "routed" | "seasonal_naive" | "zero") => hs.map((h) => growthAt(growth, name, h) ?? 0);
  const all = routes.flatMap((r) => vals(r.name as "routed"));
  const max = Math.max(...all, 1);
  const x = (i: number) => pad + (i / Math.max(1, hs.length - 1)) * (W - pad * 2);
  const y = (v: number) => H - 16 - (v / max) * (H - 30);
  const maseChamp = hs.map((h) => growthMaseAt(growth, "champion", h));
  const maseFloor = hs.map((h) => growthMaseAt(growth, "floor", h));
  const maseMax = Math.max(
    ...maseChamp.filter((v): v is number => v !== null),
    ...maseFloor.filter((v): v is number => v !== null),
    1,
  );
  const hIdx = hs.indexOf(horizon);

  return (
    <div ref={ref} className="wb-panel-viz" style={{ minHeight: 46, flex: "2 1 0" }}>
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="pooled MAE and MASE by true horizon, champion versus floor versus zero"
      >
        <text x={pad + 2} y={11} className="demo-axis-label">
          <tspan fill={C_TEAL}>routed</tspan> <tspan fill={C_GRAY}>floor</tspan>{" "}
          <tspan fill={C_AMBER}>zero</tspan> <tspan fill={C_PINK}>MASE champ/floor</tspan>
        </text>
        {routes.map((r) => (
          <polyline
            key={r.name}
            points={vals(r.name as "routed")
              .map((v, i) => `${x(i)},${y(v)}`)
              .join(" ")}
            fill="none"
            stroke={r.color}
            strokeWidth={1.5}
            strokeDasharray={r.dash}
          />
        ))}
        {hs.map((h, i) => (
          <text key={h} x={x(i)} y={H - 3} textAnchor="middle" className="demo-axis-label">
            h{h}
          </text>
        ))}
        {/* pooled MASE, normalized to its own max, same x-axis */}
        {maseChamp.some((v) => v !== null) && (
          <polyline
            points={maseChamp
              .map((v, i) => (v === null ? null : `${x(i)},${H - 16 - (v / maseMax) * (H - 30)}`))
              .filter((p): p is string => p !== null)
              .join(" ")}
            fill="none"
            stroke={C_PINK}
            strokeWidth={1.2}
          />
        )}
        {maseFloor.some((v) => v !== null) && (
          <polyline
            points={maseFloor
              .map((v, i) => (v === null ? null : `${x(i)},${H - 16 - (v / maseMax) * (H - 30)}`))
              .filter((p): p is string => p !== null)
              .join(" ")}
            fill="none"
            stroke={C_PINK}
            strokeWidth={1}
            strokeDasharray="2 3"
            opacity={0.7}
          />
        )}
        {hIdx >= 0 && (
          <line
            x1={x(hIdx)}
            x2={x(hIdx)}
            y1={14}
            y2={H - 16}
            stroke={C_PINK}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        )}
      </svg>
    </div>
  );
}

/** Order units: no decimals from 10 up so the readout chips stay on one line
 * inside the 280px band. */
function fmtUnits(v: number): string {
  return v >= 10 ? v.toFixed(0) : v.toFixed(1);
}

/** The order-up-to decision layer: service level τ → order quantity from the
 * committed τ→quantile mapping, over/under-stocked units vs the naive-floor
 * policy for the selected series' window. A labelled simulation — no savings
 * claims. */
function DecisionStrip({
  decision,
  series,
  origin,
  tau,
  onTau,
}: {
  decision: DecisionBlock;
  series: CatalogSeries;
  origin: OriginBlock | null;
  tau: number;
  onTau: (tau: number) => void;
}) {
  const blk = origin;
  const horizons = blk?.horizons ?? [];
  const routedCurve = curveAt(blk?.models.routed ?? null, 1);
  const floorCurve = curveAt(blk?.models.floor ?? null, 1);
  const ordersChamp = orderPolicy(decision, series.demand_class, "champion", routedCurve, horizons, tau);
  const ordersFloor = orderPolicy(decision, series.demand_class, "floor", floorCurve, horizons, tau);
  const costs = {
    holding: decision.cost_assumptions.holding_cost_per_unit,
    stockout: decision.cost_assumptions.stockout_cost_per_unit_short,
  };
  const win = blk
    ? policyWindow(ordersChamp, horizons, blk.actuals, costs)
    : { overUnits: 0, underUnits: 0, cost: 0 };
  const winFloor = blk
    ? policyWindow(ordersFloor, horizons, blk.actuals, costs)
    : { overUnits: 0, underUnits: 0, cost: 0 };

  return (
    <div className="wb-decision-strip">
      <div className="wb-slider-row">
        <label className="wb-rail-title" htmlFor="service-level">
          τ
        </label>
        <input
          id="service-level"
          type="range"
          className="wb-slider"
          min={0.5}
          max={0.99}
          step={0.01}
          value={tau}
          style={{ "--fill": `${((tau - 0.5) / 0.49) * 100}%` } as React.CSSProperties}
          onChange={(e) => onTau(Number(e.target.value))}
        />
        <span className="chip wb-value-badge">τ = {tau.toFixed(2)}</span>
      </div>
      <div className="demo-readouts">
        <span className="chip demo-readout">
          routed over {fmtUnits(win.overUnits)} / under {fmtUnits(win.underUnits)}
        </span>
        <span className="chip demo-readout">
          floor over {fmtUnits(winFloor.overUnits)} / under {fmtUnits(winFloor.underUnits)} · Δ{" "}
          {win.cost >= winFloor.cost ? "+" : ""}
          {(win.cost - winFloor.cost).toFixed(1)}
        </span>
      </div>
      <p className="demo-hint" title={`documented costs: ${costs.holding}/unit held, ${costs.stockout}/unit short`}>
        order-up-to simulation — no savings claims
      </p>
    </div>
  );
}
