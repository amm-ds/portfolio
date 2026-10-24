import { useMeasuredSize } from "../../charts/useMeasuredSize";
import type {
  CatalogSeries,
  DecisionBlock,
  ForecastPayload,
  HorizonGrowth,
  OriginBlock,
} from "../../types";
import { curveAt, fmtDay, growthAt, growthMaseAt, orderPolicy, policyWindow } from "../kpis";
import { Figure } from "./common";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";

/** Uncertainty & Reliability: the committed per-h coverage against its
 * target + the width trend + the calibration verdict, the horizon-growth
 * mini chart (routed vs floor vs zero), and the order-up-to decision strip. */
export function ReliabilityPanel({
  payload,
  series,
  origin,
  tau,
  onTau,
}: {
  payload: ForecastPayload;
  series: CatalogSeries;
  origin: OriginBlock | null;
  /** Service level τ (decision layer) + setter. */
  tau: number;
  onTau: (tau: number) => void;
}) {
  return (
    <Figure
      comment={
        <>
          Coverage and width of the per-h bands on the scored origins, against the{" "}
          <strong>{Math.round(payload.bands.target_coverage * 100)}% target</strong> — coverage
          and width, never looks. Below: the pooled error-growth curve the horizon slider
          demonstrates (champion vs floor), then the order-up-to decision layer.
        </>
      }
    >
      <CoverageWidth payload={payload} />
      <GrowthMini growth={payload.horizon_growth} />
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

/** Coverage bars per h + target line + width trend, stacked vertically. */
function CoverageWidth({ payload }: { payload: ForecastPayload }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 480;
  const H = size?.h ?? 150;
  const bands = payload.bands;
  const hs = Object.keys(bands.per_horizon).map(Number).sort((a, b) => a - b);
  const pad = 12;
  const labelH = 14;
  const panel = (H - pad * 2 - labelH) / 2;
  const zero2 = pad + panel;
  const groupW = (W - pad * 2) / Math.max(1, hs.length);
  const barW = Math.max(3, groupW * 0.5);
  const widths = hs.map((h) => bands.per_horizon[String(h)].avg_width);
  const maxW = Math.max(...widths, 1);
  const target = bands.target_coverage;

  return (
    <div ref={ref} className="wb-panel-viz wb-tab-viz" style={{ minHeight: 150 }}>
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
                opacity={0.85}
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
        <text x={pad + 2} y={zero2 + 12} className="demo-axis-label">
          avg band width
        </text>
        {hs.length > 1 && (
          <polyline
            points={widths
              .map(
                (w, i) =>
                  `${pad + i * groupW + groupW / 2},${zero2 + 16 + (1 - w / maxW) * (panel - 22)}`,
              )
              .join(" ")}
            fill="none"
            stroke={C_AMBER}
            strokeWidth={1.5}
          />
        )}
      </svg>
      <p className="demo-hint" style={{ padding: "2px 12px 6px" }}>
        <span className={`chip demo-readout ${bands.pooled_verdict === "calibrated" ? "good" : "bad"}`}>
          {bands.pooled_verdict}
        </span>{" "}
        pooled coverage <strong>{(bands.pooled_coverage * 100).toFixed(1)}%</strong> · erratic rows
        carry the conformal band, lumpy rows the P(sale)+ladder (no collapsing width)
      </p>
    </div>
  );
}

/** The pooled error-growth mini chart: champion (routed) vs floor vs zero. */
function GrowthMini({ growth }: { growth: HorizonGrowth }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 480;
  const H = size?.h ?? 130;
  const hs = growth.horizons;
  const pad = 12;
  const routes: Array<{ name: string; color: string; dash?: string; mase?: boolean }> = [
    { name: "routed", color: C_TEAL },
    { name: "seasonal_naive", color: C_GRAY, dash: "5 4" },
    { name: "zero", color: C_AMBER, dash: "2 4" },
  ];
  const vals = (name: "routed" | "seasonal_naive" | "zero") => hs.map((h) => growthAt(growth, name, h) ?? 0);
  const all = routes.flatMap((r) => vals(r.name as "routed"));
  const max = Math.max(...all, 1);
  const x = (i: number) => pad + (i / Math.max(1, hs.length - 1)) * (W - pad * 2 - 70);
  const y = (v: number) => H - 18 - (v / max) * (H - 36);
  const maseChamp = hs.map((h) => growthMaseAt(growth, "champion", h));
  const maseMax = Math.max(...maseChamp.filter((v): v is number => v !== null), 1);

  return (
    <div ref={ref} className="wb-panel-viz wb-tab-viz" style={{ minHeight: 130 }}>
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="pooled MAE by true horizon, champion versus floor versus zero"
      >
        <text x={pad + 2} y={12} className="demo-axis-label">
          pooled MAE by true horizon (units)
        </text>
        {routes.map((r) => (
          <polyline
            key={r.name}
            points={vals(r.name as "routed")
              .map((v, i) => `${x(i)},${y(v)}`)
              .join(" ")}
            fill="none"
            stroke={r.color}
            strokeWidth={1.6}
            strokeDasharray={r.dash}
          />
        ))}
        {hs.map((h, i) => (
          <text key={h} x={x(i)} y={H - 4} textAnchor="middle" className="demo-axis-label">
            h{h}
          </text>
        ))}
        {/* MASE panel (right): the unitless growth, same shape, separate axis */}
        <text x={W - 60} y={12} textAnchor="end" className="demo-axis-label">
          MASE
        </text>
        {maseChamp.some((v) => v !== null) && (
          <polyline
            points={maseChamp
              .map((v, i) =>
                v === null ? null : `${W - 60 + (i / Math.max(1, hs.length - 1)) * 50},${H - 18 - (v / maseMax) * (H - 36)}`,
              )
              .filter((p): p is string => p !== null)
              .join(" ")}
            fill="none"
            stroke={C_PINK}
            strokeWidth={1.4}
          />
        )}
        <text x={W - 6} y={12} textAnchor="end" className="demo-axis-label" fill={C_PINK}>
          champ
        </text>
        <text x={pad + 2} y={22} className="demo-axis-label">
          <tspan fill={C_TEAL}>routed</tspan> <tspan fill={C_GRAY}>floor</tspan>{" "}
          <tspan fill={C_AMBER}>zero</tspan>
        </text>
      </svg>
      <p className="demo-hint" style={{ padding: "2px 12px 6px" }}>
        error genuinely grows with the true horizon h — the h-slider switches between genuinely
        different direct models, not between views of one curve
      </p>
    </div>
  );
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
  const tauKey = tau.toFixed(2);
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
  const committed = decision.per_class[series.demand_class]?.[
    `tau_${(0.9).toFixed(2)}`
  ];

  return (
    <div className="wb-decision-strip">
      <div className="wb-slider-row">
        <label className="wb-rail-title" htmlFor="service-level">
          Service level τ
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
          routed policy orders: {ordersChamp.map((o) => o.toFixed(1)).join(" · ")} (h
          {horizons.join("/h")})
        </span>
        <span className="chip demo-readout">
          over {win.overUnits.toFixed(1)} / under {win.underUnits.toFixed(1)} units vs actuals
        </span>
        <span className="chip demo-readout">
          floor policy: over {winFloor.overUnits.toFixed(1)} / under {winFloor.underUnits.toFixed(1)}{" "}
          units · Δcost {win.cost >= winFloor.cost ? "+" : ""}
          {(win.cost - winFloor.cost).toFixed(1)}
        </span>
        <span className="chip demo-readout" title={decision.mapping_note}>
          order = max(point + q<sub>τ</sub>(residuals), 0) · τ grid stop {tauKey}
        </span>
      </div>
      <p className="demo-hint">
        Order-up-to <strong>simulation</strong> — {costs.holding} cost/unit held, {costs.stockout}{" "}
        cost/unit short ({costs.holding}·over + {costs.stockout}·under per cell), offsets from the
        committed selection-origin residual quantiles per class. No savings claims
        {committed && (
          <>
            {" "}
            — the committed per-class table puts the routed policy{" "}
            {committed.delta_champion_minus_floor >= 0 ? "above" : "below"} the floor policy on
            this class at τ=0.90 (see the experiment report)
          </>
        )}
        .
      </p>
      <p className="demo-hint">
        Selected: <strong>{series.label}</strong> · origin {fmtDay(blk?.origin_date ?? "")} · class{" "}
        {series.demand_class}
      </p>
    </div>
  );
}
