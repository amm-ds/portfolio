import { useMeasuredSize } from "../../charts/useMeasuredSize";
import type {
  CatalogSeries,
  DemandClass,
  ForecastPayload,
  ModelKey,
  OriginBlock,
} from "../../types";
import { curveAt, fmtDay, horizonKpi, modelBlock, routedLabel, scoreboardRow } from "../kpis";
import { MODEL_COLOR } from "./ExplorerPanel";
import { Figure } from "./common";

const C_TEAL = "#2dd4bf";
const C_GRAY = "#64748b";

const CLASSES: DemandClass[] = ["lumpy", "erratic"];
const HS = [7, 14];
const MODELS: ModelKey[] = ["zero", "routed", "champion"];

/** Model Comparison: the experiment-wide class scoreboard first (committed
 * pooled numbers + the per-series beats-floor honesty), then the selected
 * series' per-origin per-model metrics at the selected horizon — clicking a
 * model row loads its curve in the explorer. */
export function ModelComparisonPanel({
  payload,
  series,
  origin,
  model,
  horizon,
  shock,
  onPickModel,
}: {
  payload: ForecastPayload;
  series: CatalogSeries;
  origin: OriginBlock | null;
  model: ModelKey;
  horizon: number;
  shock: number;
  onPickModel: (m: ModelKey) => void;
}) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 220;
  const H = size?.h ?? 120;

  const gap = payload.headline.routing_win_lumpy;
  const perOrigin = series.origins.map((o) => ({ date: o.origin_date, blk: o }));

  return (
    <Figure
      comment={
        <>
          Top: the committed experiment-wide scoreboard — every ADI/CV² class, at h=7 and h=14.
          Beats-floor counts are per-series (honest numerator, not a pooled average); MAEs are
          pooled over series × scored origins with the 95% paired-bootstrap CI on the gap.{" "}
          {gap && (
            <>
              Routing lumpy series away from the boosted model wins{" "}
              <strong>
                +{gap.diff.toFixed(1)} MAE [{gap.ci95[0].toFixed(1)}, {gap.ci95[1].toFixed(1)}]
              </strong>{" "}
              over all-HGB.
            </>
          )}
        </>
      }
    >
      <div className="wb-cmp-wrap">
        <div className="wb-cmp-table-scroll wb-internal-scroll">
          <table className="data-table wb-cmp-table" aria-label="class scoreboard">
            <thead>
              <tr>
                <th>class</th>
                <th>h</th>
                <th>series</th>
                <th>beats floor</th>
                <th>MAE model</th>
                <th>MAE floor</th>
                <th>gap [95% CI]</th>
                <th>vs zero</th>
              </tr>
            </thead>
            <tbody>
              {CLASSES.flatMap((cls) =>
                HS.map((h) => {
                  const row = scoreboardRow(payload.class_scoreboard, cls, h);
                  if (row.modelMae === null) return null;
                  const established = row.gap !== null && !row.gap.spansZero;
                  return (
                    <tr key={`${cls}-${h}`}>
                      <th>{cls}</th>
                      <td>h={h}</td>
                      <td>{row.nSeries.toLocaleString()}</td>
                      <td>
                        {row.beatsCount !== null ? (
                          <>
                            {row.beatsCount}/{row.beatsCount === row.nSeries ? row.nSeries : row.nSeries}{" "}
                            ({row.beatsShare !== null ? `${(row.beatsShare * 100).toFixed(0)}%` : "n/a"})
                          </>
                        ) : (
                          "n/a"
                        )}
                      </td>
                      <td>{row.modelMae.toFixed(2)}</td>
                      <td>{row.floorMae !== null ? row.floorMae.toFixed(2) : "n/a"}</td>
                      <td>
                        {row.gap ? (
                          <>
                            {row.gap.diff >= 0 ? "+" : ""}
                            {row.gap.diff.toFixed(2)} [{row.gap.ci95[0].toFixed(2)},{" "}
                            {row.gap.ci95[1].toFixed(2)}]{" "}
                            <span className={`chip demo-readout ${established ? "good" : ""}`}>
                              {established ? "established" : "not established"}
                            </span>
                          </>
                        ) : (
                          "n/a"
                        )}
                      </td>
                      <td>
                        {row.vsZero ? (
                          <>
                            {row.vsZero.diff >= 0 ? "+" : ""}
                            {row.vsZero.diff.toFixed(2)}
                            {row.vsZero.spansZero ? " (~0)" : ""}
                          </>
                        ) : (
                          "n/a"
                        )}
                      </td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>
        </div>

        <div className="wb-cmp-table-scroll wb-internal-scroll">
          <table className="data-table wb-cmp-table" aria-label="per-origin model metrics">
            <thead>
              <tr>
                <th>model</th>
                {perOrigin.map((o) => (
                  <th key={o.date}>{fmtDay(o.date)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MODELS.map((mk) => {
                const label =
                  mk === "routed" ? routedLabel(series) : mk === "champion" ? "boosted HGB" : "zero";
                const disabled = mk === "champion" && series.demand_class !== "erratic";
                return (
                  <tr key={mk} className={mk === model ? "wb-cmp-active" : ""}>
                    <th>
                      <button
                        type="button"
                        className={`wb-model-pick ${mk === model ? "active" : ""}`}
                        aria-pressed={mk === model}
                        disabled={disabled}
                        title={
                          disabled
                            ? "boosted models don't serve lumpy series — see the routing note"
                            : `load the ${label} curve`
                        }
                        onClick={() => onPickModel(mk)}
                      >
                        {label}
                      </button>
                    </th>
                    {perOrigin.map(({ date, blk }) => {
                      const k = horizonKpi(blk, mk, shock, horizon);
                      return (
                        <td key={date}>
                          {k ? (
                            <>
                              <span className="wb-cmp-cell">MAE {k.mae.toFixed(2)}</span>
                              <span className="wb-cmp-cell">
                                MASE {k.mase !== null ? k.mase.toFixed(2) : "n/a"}
                              </span>
                              <span className="wb-cmp-cell">bias {signed(k.bias)}</span>
                              <span className="wb-cmp-cell">
                                WAPE {k.wape !== null ? `${(k.wape * 100).toFixed(1)}%` : "n/a"}
                              </span>
                            </>
                          ) : (
                            "n/a"
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div ref={ref} className="wb-fold-strip">
          <span className="wb-rail-title">
            routed vs floor MAE across the scored origins (h ≤ {horizon})
          </span>
          <OriginSpread origin={origin} model={model} horizon={horizon} shock={shock} W={W} H={H} />
        </div>
      </div>
      <p className="demo-hint">
        <span className="wb-legend-swatch" style={{ background: MODEL_COLOR.routed }} /> routed{" "}
        <span className="wb-legend-swatch" style={{ background: MODEL_COLOR.zero }} /> zero{" "}
        <span className="wb-legend-swatch" style={{ background: MODEL_COLOR.champion }} /> boosted
        HGB (erratic only) · metrics derived from the stored curves at h ≤ {horizon}
      </p>
    </Figure>
  );
}

function signed(v: number, digits = 2): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;
}

/** Mini strip: routed vs floor |err| at each lattice h′ ≤ horizon for the
 * selected origin — the error-growth shape at the series level. */
function OriginSpread({
  origin,
  model,
  horizon,
  shock,
  W,
  H,
}: {
  origin: OriginBlock | null;
  model: ModelKey;
  horizon: number;
  shock: number;
  W: number;
  H: number;
}) {
  if (!origin) return <p className="demo-hint">n/a — no origin block</p>;
  const mk = (m: ModelKey) =>
    origin.horizons
      .map((h, i) => ({ h, v: Math.abs((curveAt(modelBlock(origin, m), shock)[i] ?? 0) - (origin.actuals.y[h - 1] ?? 0)) }))
      .filter((p) => p.h <= horizon);
  const a = mk(model);
  const b = mk("zero");
  const max = Math.max(...a.map((p) => p.v), ...b.map((p) => p.v), 1);
  const x = (i: number) => 14 + (i / Math.max(1, a.length - 1)) * (W - 28);
  const y = (v: number) => H - 18 - (v / max) * (H - 34);
  return (
    <svg
      width="100%"
      height="100%"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="routed versus zero per-h absolute error at the selected origin"
    >
      {[0, 0.5, 1].map((t) => (
        <line
          key={t}
          x1={10}
          x2={W - 10}
          y1={y(t * max)}
          y2={y(t * max)}
          stroke="var(--border)"
          strokeOpacity={0.5}
        />
      ))}
      <polyline
        points={a.map((p, i) => `${x(i)},${y(p.v)}`).join(" ")}
        fill="none"
        stroke={MODEL_COLOR[model]}
        strokeWidth={1.6}
      />
      <polyline
        points={b.map((p, i) => `${x(i)},${y(p.v)}`).join(" ")}
        fill="none"
        stroke={C_GRAY}
        strokeWidth={1.2}
        strokeDasharray="4 3"
      />
      {a.map((p, i) => (
        <text key={p.h} x={x(i)} y={H - 4} textAnchor="middle" className="demo-axis-label">
          h{p.h}
        </text>
      ))}
      <text x={W - 12} y={12} textAnchor="end" className="demo-axis-label">
        {model} solid · zero dashed
      </text>
    </svg>
  );
}

// re-export for the workbench's legend reuse
export { C_TEAL };
