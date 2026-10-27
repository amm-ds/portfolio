import type { ReactNode } from "react";
import { LineChart, type LineMarker } from "../charts/LineChart";
import type { HierNode, HierOrigin, HierVariant } from "../types";
import { axisFor, fmtDay, isBottom, valuesOnAxis } from "./kpis";

const C_WHITE = "#f8fafc";
const C_GREY = "#64748b";
const C_TEAL = "#2dd4bf";
const C_AMBER = "#fbbf24";
const C_PINK = "#f472b6";
const C_VIOLET = "#a78bfa";

/** Curve-variant palette: the raw global model carries the accent; the two
 * reconciled curves get two distinct hues (BottomUp amber, MinT pink); the
 * naive baseline is dashed grey, auto_ets a thin violet. */
export const VARIANT_COLOR: Record<HierVariant, string> = {
  seasonal_naive: C_GREY,
  auto_ets: C_VIOLET,
  lgbm_global: C_TEAL,
  "lgbm_global+bottom_up": C_AMBER,
  "lgbm_global+mint_shrink": C_PINK,
};

export const VARIANT_SHORT: Record<HierVariant, string> = {
  seasonal_naive: "seasonal naive",
  auto_ets: "auto ets",
  lgbm_global: "lgbm global (raw)",
  "lgbm_global+bottom_up": "lgbm global + BottomUp",
  "lgbm_global+mint_shrink": "lgbm global + MinT",
};

const VARIANTS: HierVariant[] = [
  "seasonal_naive",
  "auto_ets",
  "lgbm_global",
  "lgbm_global+bottom_up",
  "lgbm_global+mint_shrink",
];

/** Card with the shared figure-card chrome (chart region + commentary band). */
export function Figure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

/** The reconciliation canvas: history up to the origin period (bounded 2-season
 * window), the horizon actuals as a ghost overlay, and the 5 committed curves.
 * At parent nodes the raw global curve drifts off its children while the two
 * reconciled curves snap back — that gap is the story. At bottom nodes the
 * three lgbm curves coincide: reconciliation leaves bottom series unchanged. */
export function HierarchyChart({
  node,
  origin,
  horizon,
}: {
  node: HierNode;
  origin: HierOrigin | null;
  horizon: number;
}) {
  const axis = axisFor(origin);
  const total = axis.length;
  const hist = origin?.history ?? { dates: [], y: [] };
  const actuals = origin?.actuals ?? { dates: [], y: [] };
  const histVals = valuesOnAxis(axis, hist.dates, hist.y);
  const actualVals = valuesOnAxis(axis, actuals.dates, actuals.y);

  const curveVals = (v: HierVariant): number[] => {
    if (!origin) return Array<number>(total).fill(NaN);
    const blk = origin.models[v];
    return valuesOnAxis(axis, actuals.dates, blk?.y_pred ?? []);
  };

  // the origin period is the last history slot; curves start the period after
  const originIdx = origin && hist.dates.length > 0 ? hist.dates.length - 1 : undefined;
  const markers: LineMarker[] = [];
  if (originIdx !== undefined && origin) {
    markers.push({
      xIndex: originIdx,
      label: `forecast origin · ${fmtDay(origin.origin)}`,
      style: "dashed",
    });
  }

  const bottom = isBottom(node);
  const gap = (v: HierVariant): number | null => {
    if (!origin) return null;
    const raw = origin.models.lgbm_global?.y_pred;
    const rec = origin.models[v]?.y_pred;
    if (!raw || !rec || raw.length !== rec.length) return null;
    let sum = 0;
    for (let i = 0; i < raw.length; i++) sum += Math.abs(raw[i] - rec[i]);
    return sum / raw.length;
  };
  const buGap = gap("lgbm_global+bottom_up");
  const mintGap = gap("lgbm_global+mint_shrink");

  return (
    <Figure
      comment={
        bottom ? (
          <>
            A bottom series: <strong>{VARIANT_SHORT.lgbm_global}</strong> and{" "}
            <strong>{VARIANT_SHORT["lgbm_global+bottom_up"]}</strong> coincide here and{" "}
            <strong>{VARIANT_SHORT["lgbm_global+mint_shrink"]}</strong> sits almost on top —
            reconciliation leaves bottom series unchanged (BottomUp rebuilds the aggregates
            from these leaves; MinT only nudges what covariance justifies).
          </>
        ) : (
          <>
            The gap is the story: the raw global model forecasts this node on its own,
            ignoring its children, while the reconciled curves are re-anchored to them —
            mean |raw − reconciled| over the horizon: BottomUp{" "}
            <strong>{buGap !== null ? buGap.toFixed(1) : "n/a"}</strong> · MinT{" "}
            <strong>{mintGap !== null ? mintGap.toFixed(1) : "n/a"}</strong>. Which
            re-anchoring is closer to what materialized decides the value of coherence.
          </>
        )
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">{node.level}</span>
        <span className="chip demo-readout">origin {fmtDay(origin?.origin ?? "")}</span>
        <span className="chip demo-readout">h = 1…{horizon}</span>
        <span className="chip demo-readout">
          {node.children_count} {node.children_count === 1 ? "child" : "children"}
        </span>
      </div>
      <div className="demo-chart">
        <LineChart
          x={Array.from({ length: total }, (_, i) => i)}
          series={[
            { name: "history", color: C_WHITE, values: histVals },
            { name: "actuals", color: C_WHITE, dashed: true, values: actualVals },
            ...VARIANTS.map((v) => ({
              name: VARIANT_SHORT[v],
              color: VARIANT_COLOR[v],
              dashed: v === "seasonal_naive",
              width: v === "auto_ets" ? 1.25 : 2,
              values: curveVals(v),
            })),
          ]}
          markers={markers}
          xTicks={6}
          formatX={(i) => fmtDay(axis[Math.round(i)] ?? "")}
          ariaLabel={`hierarchical forecast curves at ${node.level} with history and actuals`}
        />
      </div>
      <p className="demo-hint">
        history solid · actuals ghost dashed ·{" "}
        {VARIANTS.map((v, i) => (
          <span key={v} style={{ color: VARIANT_COLOR[v] }}>
            {VARIANT_SHORT[v]}
            {i < VARIANTS.length - 1 ? " · " : ""}
          </span>
        ))}
      </p>
    </Figure>
  );
}
