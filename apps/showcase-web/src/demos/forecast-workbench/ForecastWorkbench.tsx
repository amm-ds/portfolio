import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { forecastDemand } from "../../api";
import { LineChart, type LineMarker } from "../charts/LineChart";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type {
  CatalogSeries,
  DemoManifest,
  ForecastPayload,
  ModelKey,
  OriginLabel,
} from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import {
  LIVE_HORIZONS,
  ORIGIN_INDEX,
  ORIGIN_LABELS,
  coverageNote,
  dayErrors,
  deriveFeatures,
  fmtDay,
  horizonStats,
  originBlock,
  originPctThroughHistory,
  pctEdge,
  windowMetrics,
} from "./kpis";
import { fetchForecastPayload, fetchManifest } from "./payload";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";
const C_WHITE = "#f8fafc";

const MODELS: ModelKey[] = ["naive", "champion", "challenger"];
const MODEL_COLOR: Record<ModelKey, string> = {
  naive: C_GRAY,
  champion: C_TEAL,
  challenger: C_PINK,
};
/** Consistent over/under scheme: over-forecast pink, under-forecast teal. */
const C_OVER = C_PINK;
const C_UNDER = C_TEAL;

const CLASSES: Array<CatalogSeries["demand_class"] | "all"> = [
  "all",
  "smooth",
  "intermittent",
  "sparse",
];

const TABS = ["model comparison", "error analysis", "uncertainty & reliability"] as const;
type Tab = (typeof TABS)[number];

/** Signed number with an explicit + sign (bias readouts). */
function signed(v: number, digits = 1): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;
}

/** Percent by which the champion beats the naive floor at an origin; null
 * when it can't be scored (zero floor or a missing block). */
function originEdge(series: CatalogSeries, origin: OriginLabel): number | null {
  const blk = originBlock(series, origin);
  return pctEdge(windowMetrics(blk, "champion")?.mae, windowMetrics(blk, "naive")?.mae);
}

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, pick a rolling origin — early, middle, or the frozen test window — stretch the horizon, and stress the recent demand; watch the champion, the challenger, the band, and the baseline respond.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "frozen test-window MAE (origin-4 holdout), champion vs strongest floor",
    value: "9.54 vs 11.32 seasonal-naive (-15.7%)",
    ci: "no run clears MASE 1 on the frozen test window — lgbm_tuned is closest at 1.076, champion hgb_tuned 1.078",
  },
  scenarios: [
    { name: "base", controls: { series: "United Kingdom|85123A", origin: "test", horizon: 7, spike: 1.0 } },
    { name: "sparse-series", controls: { series: "United Kingdom|84077", origin: "test", horizon: 7, spike: 1.0 } },
    { name: "early-origin", controls: { series: "United Kingdom|85123A", origin: "early", horizon: 7, spike: 1.0 } },
    { name: "spike", controls: { series: "United Kingdom|85123A", origin: "test", horizon: 7, spike: 1.5 } },
  ],
  live_endpoints: [
    {
      method: "POST",
      path: "/projects/02-demand-forecasting/forecast",
      label: "live what-if scoring",
      cost: "free-local",
    },
  ],
  payload: { path: "reports/demo_payload.json", schema_version: 2, required_keys: [] },
};

/** One string control serialized to the URL query (`?series=&origin=&model=`),
 * mirroring useControlState's write-and-cleanup pattern for the numeric ones. */
function useQueryParam<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    const q = new URLSearchParams(window.location.search).get(key);
    return (allowed as readonly string[]).includes(q ?? "") ? (q as T) : fallback;
  });
  const set = (v: T) => {
    setValue(v);
    try {
      const params = new URLSearchParams(window.location.search);
      if (v === fallback) params.delete(key);
      else params.set(key, v);
      const qs = params.toString();
      window.history.replaceState(null, "", window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash);
    } catch {
      // URL state is a nicety, never a crash
    }
  };
  return [value, set];
}

/** Card with the shared figure-card chrome (chart region + commentary band). */
function Figure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

/** Tiny inline sparkline for picker rows (drawn from the SELECTED ORIGIN's
 * as-of history, so a row previews exactly what the explorer would show). */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  const W = 64;
  const H = 20;
  const max = Math.max(...values, 1);
  const pts = values
    .map(
      (v, i) =>
        `${((i / Math.max(1, values.length - 1)) * W).toFixed(1)},${(
          H -
          (Math.max(0, v) / max) * (H - 2) -
          1
        ).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg width={W} height={H} className="wb-spark" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

type LiveState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; values: number[] }
  | { status: "unavailable" };

// --- forecast explorer (canvas) ------------------------------------------------

/** The as-of-origin canvas: history left of the marker, the selected model's
 * fan over the horizon window, the window's actuals as a ghost overlay, and
 * the embargo gap (everything between marker and window) shaded — the model
 * never saw those days. */
function ExplorerPanel({
  series,
  origin,
  model,
  horizon,
  spike,
  live,
  highlightDay,
}: {
  series: CatalogSeries;
  origin: OriginLabel;
  model: ModelKey;
  horizon: number;
  spike: number;
  live: LiveState;
  highlightDay: number | null;
}) {
  const blk = originBlock(series, origin);
  const H = Math.min(horizon, blk?.actuals.y.length ?? horizon);
  const hist = blk?.history ?? { dates: [], y: [] };
  const actuals = blk?.actuals ?? { dates: [], y: [] };
  const pred = blk?.models[model]?.y_pred ?? [];
  const band = model === "champion" ? blk?.models.champion : undefined;

  // contiguous daily axis from the origin history's first day through the
  // window's last day — the embargo gap is real axis, not a bridged line
  const axisDates = useMemo(() => {
    if (!blk || hist.dates.length === 0 || actuals.dates.length === 0) return [] as string[];
    const out: string[] = [];
    const d = new Date(hist.dates[0]);
    const end = new Date(actuals.dates[actuals.dates.length - 1]);
    while (d <= end) {
      out.push(
        `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
          d.getDate(),
        ).padStart(2, "0")}`,
      );
      d.setDate(d.getDate() + 1);
    }
    return out;
  }, [blk, hist.dates, actuals.dates]);
  const idx = useMemo(() => new Map(axisDates.map((d, i) => [d, i])), [axisDates]);

  const nan = (k: number) => Array<number>(Math.max(0, k)).fill(NaN);
  const at = (dates: string[], vals: number[], total: number): number[] => {
    const out = nan(total);
    for (let i = 0; i < dates.length; i++) {
      const j = idx.get(dates[i]);
      if (j !== undefined) out[j] = vals[i];
    }
    return out;
  };
  const total = axisDates.length;
  const histVals = at(hist.dates, hist.y, total);
  const actualVals = at(actuals.dates, actuals.y, total);
  const predVals = nan(total);
  const p10Vals = nan(total);
  const p90Vals = nan(total);
  for (let h = 1; h <= H; h++) {
    const j = idx.get(actuals.dates[h - 1]);
    if (j === undefined) continue;
    predVals[j] = pred[h - 1];
    if (band?.p10 && band?.p90) {
      p10Vals[j] = band.p10[h - 1];
      p90Vals[j] = band.p90[h - 1];
    }
  }
  const liveVals =
    live.status === "ok"
      ? at(actuals.dates.slice(0, live.values.length), live.values, total)
      : null;

  const originIdx = hist.dates.length ? idx.get(hist.dates[hist.dates.length - 1]) : undefined;
  const windowStart = actuals.dates.length ? idx.get(actuals.dates[0]) : undefined;

  const sliceMax = (arr: number[]) => Math.max(...arr.slice(0, H), 0);
  const cMax = Math.max(
    ...hist.y,
    sliceMax(pred),
    band?.p90 ? sliceMax(band.p90) : 0,
    ...actuals.y,
    live.status === "ok" ? Math.max(...live.values) : 0,
    1,
  ) * 1.08;

  const x = Array.from({ length: total }, (_, i) => i);

  const markers: LineMarker[] = [];
  if (originIdx !== undefined) {
    markers.push({ xIndex: originIdx, label: `forecast origin · ${fmtDay(blk!.origin_date)}`, style: "dashed" });
  }
  if (highlightDay !== null && windowStart !== undefined) {
    markers.push({
      xIndex: windowStart + highlightDay - 1,
      label: `h=${highlightDay}`,
      style: "solid",
      color: C_PINK,
      top: false,
    });
  }

  // The p10/p90 band and the embargo shade live on an overlay SVG with the
  // same padding/scale math as LineChart (pad + yMax passed explicitly).
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const pad = { l: 52, r: 18, t: 16, b: 32 };
  const W = size?.w ?? 720;
  const Hpx = size?.h ?? 280;
  const plotW = W - pad.l - pad.r;
  const plotH = Hpx - pad.t - pad.b;
  const px = (i: number) => pad.l + (i / Math.max(1, total - 1)) * plotW;
  const py = (v: number) => pad.t + plotH - (v / cMax) * plotH;

  let bandPath: string | null = null;
  if (band?.p10 && band?.p90 && windowStart !== undefined) {
    const fwd = Array.from({ length: H }, (_, k) => `${px(windowStart + k).toFixed(1)},${py(band.p90![k]).toFixed(1)}`);
    const back = Array.from({ length: H }, (_, k) => `${px(windowStart + H - 1 - k).toFixed(1)},${py(band.p10![H - 1 - k]).toFixed(1)}`);
    bandPath = `M${fwd.join(" L")} L${back.join(" L")} Z`;
  }

  const stats = horizonStats(blk, model, H);
  const naiveStats = horizonStats(blk, "naive", H);

  return (
    <Figure
      comment={
        <>
          As of <strong>{fmtDay(blk?.origin_date ?? "")}</strong>, only the history left of the
          marker was known — everything right of it was unknown on that date. The{" "}
          <strong>{model}</strong> curve is a historical backtest against the frozen window, not a
          live prediction{model === "champion" && band ? ", with the committed p10–p90 band" : ""}.
          {live.status === "ok" && (
            <> The amber dashes are live re-scores of the first {LIVE_HORIZONS.length} window days
            with the recent-demand spike applied.</>
          )}
        </>
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">{series.label}</span>
        <span className="chip demo-readout">{series.demand_class}</span>
        <span className="chip demo-readout">origin {fmtDay(blk?.origin_date ?? "")}</span>
        <span className="chip demo-readout">horizon {H}d</span>
        <span className="chip demo-readout">{model}</span>
        <span className="chip demo-readout">spike ×{spike.toFixed(1)}</span>
        {highlightDay !== null && (
          <span className="chip demo-readout" style={{ color: C_PINK }}>
            error day h={highlightDay}
          </span>
        )}
        {stats?.mase == null ? (
          <span className="chip demo-readout">MASE n/a — zero-scale window</span>
        ) : (
          <span className={`chip demo-readout ${stats.mase < 1 ? "good" : "bad"}`}>
            MASE {stats.mase.toFixed(2)} — {stats.mase < 1 ? "beats" : "trails"} naive
            {naiveStats?.mase != null && ` (${naiveStats.mase.toFixed(2)})`}
          </span>
        )}
      </div>
      <div className="demo-chart">
        <div ref={ref} className="wb-fan">
          <LineChart
            x={x}
            series={[
              { name: "history", color: C_WHITE, values: histVals },
              {
                name: model,
                color: MODEL_COLOR[model],
                dashed: model !== "champion",
                values: predVals,
              },
              ...(liveVals
                ? [{ name: "live re-score", color: C_AMBER, dashed: true, values: liveVals }]
                : []),
              { name: "actuals", color: C_WHITE, dashed: true, values: actualVals },
            ]}
            yMax={cMax}
            pad={pad}
            markers={markers}
            xTicks={6}
            formatX={(i) => fmtDay(axisDates[Math.round(i)] ?? "")}
            ariaLabel="as-of-origin demand history with forecast fan and ghost actuals"
          />
          <svg
            className="wb-fan-band"
            width="100%"
            height="100%"
            viewBox={`0 0 ${W} ${Hpx}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {originIdx !== undefined && windowStart !== undefined && windowStart - 1 > originIdx && (
              <g>
                <rect
                  x={px(originIdx)}
                  y={pad.t}
                  width={Math.max(0, px(windowStart - 1) - px(originIdx))}
                  height={plotH}
                  fill={C_WHITE}
                  fillOpacity={0.04}
                />
                <text
                  x={(px(originIdx) + px(windowStart - 1)) / 2}
                  y={pad.t + 10}
                  textAnchor="middle"
                  className="demo-axis-label"
                >
                  embargo
                </text>
              </g>
            )}
            {bandPath && (
              <path d={bandPath} fill={C_TEAL} fillOpacity={0.15} />
            )}
          </svg>
        </div>
      </div>
      <p className="demo-hint">
        {live.status === "ok"
          ? `amber fan: live re-score (h=1–${LIVE_HORIZONS.length}); teal band shows the committed backtest`
          : live.status === "loading"
            ? "re-scoring the window days live…"
            : `history solid white · ${model} ${model === "champion" ? "solid + band" : "dashed"} · actuals ghost dashed`}
      </p>
    </Figure>
  );
}

// --- secondary band: tabbed views ----------------------------------------------

/** Model Comparison: the three candidates' committed window metrics across
 * the three origins (naive first), a fold-spread strip for the selected
 * series, and click-a-model-row → sets the model chip. */
function ModelComparisonView({
  series,
  model,
  onPickModel,
}: {
  series: CatalogSeries;
  model: ModelKey;
  onPickModel: (m: ModelKey) => void;
}) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 220;
  const H = size?.h ?? 120;
  const metricFmt = (v: number | null, digits: number) => (v == null ? "n/a" : v.toFixed(digits));
  const metricRows: Array<{ key: "mae" | "mase" | "bias" | "wape"; label: string; digits: number }> = [
    { key: "mae", label: "MAE", digits: 2 },
    { key: "mase", label: "MASE", digits: 2 },
    { key: "bias", label: "bias", digits: 2 },
    { key: "wape", label: "WAPE", digits: 2 },
  ];

  // fold spread: the champion's committed MAE across the three origins
  const perOriginMae = ORIGIN_LABELS.map(
    (l) => windowMetrics(originBlock(series, l), "champion")?.mae ?? null,
  );
  const valid = perOriginMae.filter((v): v is number => v !== null);
  const spreadPct =
    valid.length === 3 && valid.some((v) => v > 0)
      ? ((Math.max(...valid) - Math.min(...valid)) / (valid.reduce((a, b) => a + b, 0) / 3)) * 100
      : null;

  return (
    <Figure
      comment={
        <>
          Committed 14-day window metrics per origin — identical origins and horizons for
          every candidate: the frozen protocol. Click a model to load its curve in the
          explorer.
        </>
      }
    >
      <div className="wb-cmp-wrap">
        <div className="wb-cmp-table-scroll wb-internal-scroll">
          <table className="data-table wb-cmp-table">
            <thead>
              <tr>
                <th>model</th>
                {ORIGIN_LABELS.map((l) => (
                  <th key={l}>
                    {l}
                    {l === "test" ? " · frozen" : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MODELS.map((mk) => (
                <tr key={mk} className={mk === model ? "wb-cmp-active" : ""}>
                  <th>
                    <button
                      type="button"
                      className={`wb-model-pick ${mk === model ? "active" : ""}`}
                      aria-pressed={mk === model}
                      onClick={() => onPickModel(mk)}
                    >
                      {mk}
                    </button>
                  </th>
                  {ORIGIN_LABELS.map((l) => {
                    const m = windowMetrics(originBlock(series, l), mk);
                    return (
                      <td key={l}>
                        {m
                          ? metricRows.map((r) => (
                              <span key={r.key} className="wb-cmp-cell">
                                {r.label} {metricFmt(m[r.key], r.digits)}
                              </span>
                            ))
                          : "n/a"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div ref={ref} className="wb-fold-strip">
          <span className="wb-rail-title">fold spread — champion MAE</span>
          {spreadPct === null ? (
            <p className="demo-hint">n/a — a zero-scale window makes MAE uninformative here</p>
          ) : (
            <svg
              width="100%"
              height="100%"
              viewBox={`0 0 ${W} ${H}`}
              preserveAspectRatio="none"
              role="img"
              aria-label="champion MAE spread across the three origins"
            >
              <line
                x1={10}
                y1={H / 2 - 6}
                x2={W - 10}
                y2={H / 2 - 6}
                stroke="var(--border)"
              />
              {(() => {
                const lo = Math.min(...perOriginMae.map((v) => v ?? 0));
                const hi = Math.max(...perOriginMae.map((v) => v ?? 0));
                const span = hi - lo || 1;
                return perOriginMae.map((v, i) => {
                  if (v === null) return null;
                  const cx = 10 + ((v - lo) / span) * (W - 20);
                  return (
                    <g key={ORIGIN_LABELS[i]}>
                      <circle cx={cx} cy={H / 2 - 6} r={4} fill={C_TEAL} />
                      <text x={cx} y={H / 2 + 12} textAnchor="middle" className="demo-axis-label">
                        {ORIGIN_LABELS[i]}
                      </text>
                      <text x={cx} y={H / 2 + 24} textAnchor="middle" className="demo-axis-label">
                        {v.toFixed(1)}
                      </text>
                    </g>
                  );
                });
              })()}
              {spreadPct !== null && (
                <text x={W - 10} y={12} textAnchor="end" className="demo-axis-label">
                  spread {spreadPct.toFixed(0)}%
                </text>
              )}
            </svg>
          )}
        </div>
      </div>
      <p className="demo-hint">
        <span className="wb-legend-swatch" style={{ background: C_TEAL }} /> champion{" "}
        <span className="wb-legend-swatch" style={{ background: C_PINK }} /> challenger{" "}
        <span className="wb-legend-swatch" style={{ background: C_GRAY }} /> naive floor
      </p>
    </Figure>
  );
}

/** Error Analysis: per-horizon-day |error| bars colored by sign (over pink /
 * under teal), the worst day annotated, an over/under split summary, and
 * click-a-day → highlights that day in the explorer canvas. All derived
 * client-side from the committed curve vs the origin's actuals. */
function ErrorAnalysisView({
  series,
  origin,
  model,
  highlightDay,
  onHighlight,
}: {
  series: CatalogSeries;
  origin: OriginLabel;
  model: ModelKey;
  highlightDay: number | null;
  onHighlight: (h: number | null) => void;
}) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 480;
  const H = size?.h ?? 120;
  const errs = dayErrors(originBlock(series, origin), model);
  const max = Math.max(...errs.map((e) => e.abs), 1);
  const pad = 12;
  const labelH = 14;
  const plotH = H - pad * 2 - labelH;
  const groupW = (W - pad * 2) / Math.max(1, errs.length);
  const barW = Math.max(2, groupW * 0.55);
  const worst = errs.reduce((a, b) => (b.abs > a.abs ? b : a), errs[0] ?? null);
  const overN = errs.filter((e) => e.over).length;
  const meanAbs = errs.length ? errs.reduce((a, e) => a + e.abs, 0) / errs.length : 0;

  return (
    <Figure
      comment={
        <>
          Per-day |error| for the <strong>{model}</strong> at the <strong>{origin}</strong> origin
          — derived from the committed curve against the window's actuals. Over-forecasts in pink,
          under-forecasts in teal; click a day to pin it on the explorer.
        </>
      }
    >
      <div ref={ref} className="wb-panel-viz wb-tab-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="absolute error by horizon day, colored by sign"
        >
          {errs.map((e) => {
            const x0 = pad + (e.h - 1) * groupW;
            const bh = (e.abs / max) * plotH;
            const base = pad + plotH;
            return (
              <g key={e.h}>
                <rect
                  x={x0 + (groupW - barW) / 2}
                  y={base - bh}
                  width={barW}
                  height={Math.max(bh, e.abs > 0 ? 1.5 : 0)}
                  fill={e.over ? C_OVER : C_UNDER}
                  opacity={highlightDay === e.h ? 1 : 0.8}
                  stroke={highlightDay === e.h ? C_WHITE : "none"}
                  strokeWidth={highlightDay === e.h ? 1.5 : 0}
                  style={{ cursor: "pointer" }}
                  onClick={() => onHighlight(highlightDay === e.h ? null : e.h)}
                />
                <text x={x0 + groupW / 2} y={H - 2} textAnchor="middle" className="demo-axis-label">
                  {e.h % 2 === 1 ? `h${e.h}` : ""}
                </text>
                {worst && e.h === worst.h && e.abs > 0 && (
                  <text
                    x={x0 + groupW / 2}
                    y={Math.max(10, base - bh - 4)}
                    textAnchor="middle"
                    className="demo-axis-label"
                  >
                    worst
                  </text>
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
          {overN} of {errs.length} days
        </strong>{" "}
        ({errs.length ? Math.round((overN / errs.length) * 100) : 0}%) · mean |err|{" "}
        <strong>{meanAbs.toFixed(1)}</strong> units
        {worst && worst.abs > 0 && (
          <>
            {" "}
            · worst <strong>h={worst.h}</strong> ({worst.abs.toFixed(1)} units{" "}
            {worst.over ? "over" : "under"})
          </>
        )}
      </p>
    </Figure>
  );
}

/** Uncertainty & Reliability: per-horizon empirical coverage of the committed
 * band against its target, the interval-width trend, and the calibration
 * verdict. Coverage and width, never looks. */
function UncertaintyView({ payload }: { payload: ForecastPayload }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 480;
  const H = size?.h ?? 120;
  const band = payload.scalars.band;
  if (!band) {
    return (
      <Figure comment={<>No probabilistic report committed for this track.</>}>
        <p className="demo-hint">n/a</p>
      </Figure>
    );
  }
  const cov = band.horizon_coverage;
  const width = band.horizon_avg_width;
  const target = band.target_coverage;
  const pad = 12;
  const labelH = 14;
  const plotH = (H - pad * 2 - labelH) / 2;
  const half = Math.floor((H - pad * 2 - labelH) / 2) + pad;
  const groupW = (W - pad * 2) / Math.max(1, cov.length);
  const barW = Math.max(2, groupW * 0.55);
  const degenerate = width.every((w) => w <= 0);
  const maxW = Math.max(...width, 1);
  const verdict = degenerate
    ? "conservative — but degenerate: the band collapses to zero width on zero-demand days"
    : (band.calibration_verdict ?? "uncommitted");

  return (
    <Figure
      comment={
        <>
          Empirical per-horizon coverage of the committed p10–p90 band against its{" "}
          <strong>{Math.round(target * 100)}% target</strong>, plus the interval-width trend —
          coverage and width, never looks.
        </>
      }
    >
      <div ref={ref} className="wb-panel-viz wb-tab-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="per-horizon coverage vs target and interval width trend"
        >
          {/* coverage bars + target line */}
          {cov.map((c, i) => {
            const x0 = pad + i * groupW;
            const bh = Math.min(c, 1) * plotH;
            return (
              <g key={`c${i}`}>
                <rect
                  x={x0 + (groupW - barW) / 2}
                  y={pad + plotH - bh}
                  width={barW}
                  height={Math.max(bh, c > 0 ? 1.5 : 0)}
                  fill={C_TEAL}
                  opacity={0.85}
                />
                {i % 2 === 0 && (
                  <text x={x0 + groupW / 2} y={pad + plotH + 12} textAnchor="middle" className="demo-axis-label">
                    h{i + 1}
                  </text>
                )}
              </g>
            );
          })}
          <line
            x1={pad}
            y1={pad + plotH - target * plotH}
            x2={W - pad}
            y2={pad + plotH - target * plotH}
            stroke={C_GRAY}
            strokeDasharray="4 4"
          />
          <text x={pad + 2} y={pad + plotH - target * plotH - 3} className="demo-axis-label">
            target {(target * 100).toFixed(0)}%
          </text>
          {/* width trend */}
          <text x={pad + 2} y={half + 10} className="demo-axis-label">
            interval width{degenerate ? " — 0 everywhere (degenerate)" : ""}
          </text>
          {width.length > 1 && (
            <polyline
              points={width
                .map(
                  (w, i) =>
                    `${pad + (i / (width.length - 1)) * (W - pad * 2)},${half + 14 + (1 - w / maxW) * (plotH - 18)}`,
                )
                .join(" ")}
              fill="none"
              stroke={C_AMBER}
              strokeWidth={1.5}
            />
          )}
        </svg>
      </div>
      <p className="demo-hint">
        <span className={`chip demo-readout ${degenerate ? "bad" : "good"}`}>{verdict}</span>{" "}
        pooled coverage <strong>{(band.quantile_coverage_pooled * 100).toFixed(1)}%</strong>
      </p>
    </Figure>
  );
}

// --- notice tiles --------------------------------------------------------------

/** Origin-context tile: the champion's MAE edge over the naive floor at the
 * early origin vs the frozen test window — fold spread matters more than
 * averages. */
function OriginContextText({
  series,
  origin,
}: {
  series: CatalogSeries;
  origin: OriginLabel;
}) {
  const eEarly = originEdge(series, "early");
  const eTest = originEdge(series, "test");
  const phrase = (v: number | null) =>
    v === null
      ? "can't be scored on a zero seasonal scale"
      : v >= 0
        ? `wins by ${Math.round(v)}%`
        : `trails by ${Math.round(-v)}%`;
  if (eEarly === null || eTest === null) {
    return (
      <>
        At the <strong>{origin}</strong> origin MASE can't be scored on a{" "}
        <strong>zero seasonal scale</strong> — the fold spread is undefined for this series, so the
        band, not the point, is the honest signal
      </>
    );
  }
  const direction =
    eTest === eEarly ? "holds" : eTest < eEarly ? "narrows to" : "widens to";
  return (
    <>
      At the <strong>early</strong> origin the champion {phrase(eEarly)} MAE; at the{" "}
      <strong>frozen test window</strong> the gap {direction}{" "}
      <strong>
        {Math.abs(Math.round(eTest))}% vs a much harder seasonal floor
      </strong>{" "}
      — fold spread matters more than averages
    </>
  );
}

/** Model-verdict tile: the selected model vs the naive floor at this origin —
 * MAE edge, MASE, and the bias sign. */
function ModelVerdictText({
  series,
  origin,
  model,
}: {
  series: CatalogSeries;
  origin: OriginLabel;
  model: ModelKey;
}) {
  const blk = originBlock(series, origin);
  const m = windowMetrics(blk, model);
  const nv = windowMetrics(blk, "naive");
  if (!m || !nv) {
    return (
      <>
        No committed window for the <strong>{model}</strong> at the <strong>{origin}</strong>{" "}
        origin — pick another series or origin
      </>
    );
  }
  const edge = pctEdge(m.mae, nv.mae);
  const meanAct = blk!.actuals.y.length
    ? blk!.actuals.y.reduce((a, b) => a + b, 0) / blk!.actuals.y.length
    : 0;
  const biasPct = meanAct > 0 ? (m.bias / meanAct) * 100 : null;
  const name = model.charAt(0).toUpperCase() + model.slice(1);
  const edgeClause =
    edge === null
      ? "matches the naive floor"
      : edge >= 0
        ? `beats naive by ${Math.round(edge)}%`
        : `trails naive by ${Math.round(-edge)}%`;
  const maseClause = m.mase != null ? ` (MASE ${m.mase.toFixed(2)})` : "";
  const biasClause =
    biasPct !== null && Math.abs(biasPct) >= 0.05
      ? `; bias ${signed(biasPct, 0)}% — it ${m.bias > 0 ? "over" : "under"}-forecasts on this series`
      : "";
  return (
    <>
      <strong>
        {name} {edgeClause}
      </strong>{" "}
      MAE at this origin{maseClause}
      {biasClause}
    </>
  );
}

// --- demo -------------------------------------------------------------------------

export default function ForecastWorkbench() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<ForecastPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchManifest("forecast-workbench")
      .then((m) => !cancelled && setManifest(m))
      .catch(() => {
        /* payload fetch below reports the real error */
      });
    fetchForecastPayload("forecast-workbench")
      .then((p) => !cancelled && setPayload(p))
      .catch(() => !cancelled && setError("could not load the demo payload — is the API running?"));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <div className="state-box error">{error}</div>;
  }
  if (payload === null) {
    return <p className="loading">loading demo…</p>;
  }
  return <Workbench manifest={manifest ?? FALLBACK_MANIFEST} payload={payload} />;
}

/** Workbench body once the payload (and manifest, or fallback) is in hand. */
function Workbench({ manifest, payload }: { manifest: DemoManifest; payload: ForecastPayload }) {
  const state = useControlState({ horizon: 7, spike: 1.0 }, manifest.scenarios);
  const { controls, setControl } = state;
  const horizon = controls.horizon ?? 7;
  const spike = controls.spike ?? 1.0;

  // string controls serialize to the same query string as the numeric ones
  const defaultId = payload.catalog[0]?.series_id ?? "";
  const [seriesId, setSeriesId] = useQueryParam(
    "series",
    payload.catalog.map((s) => s.series_id),
    defaultId,
  );
  const [origin, setOrigin] = useQueryParam("origin", ORIGIN_LABELS, "test" as OriginLabel);
  const [model, setModel] = useQueryParam("model", MODELS, "champion" as ModelKey);
  const series =
    payload.catalog.find((s) => s.series_id === seriesId) ?? payload.catalog[0];
  const originBlk = originBlock(series, origin);
  const originPct = originPctThroughHistory(payload, origin);

  // --- series picker filtering (sparklines use the SELECTED ORIGIN's history)
  const [clsFilter, setClsFilter] = useState<"all" | CatalogSeries["demand_class"]>("all");
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return payload.catalog.filter(
      (s) =>
        (clsFilter === "all" || s.demand_class === clsFilter) &&
        (q === "" || s.label.toLowerCase().includes(q) || s.series_id.toLowerCase().includes(q)),
    );
  }, [payload.catalog, clsFilter, search]);

  // --- secondary band tabs + error-click highlight
  const [tab, setTab] = useState<Tab>("model comparison");
  const [highlightDay, setHighlightDay] = useState<number | null>(null);
  useEffect(() => {
    setHighlightDay(null);
  }, [series.series_id, origin]);

  // --- live spike re-scoring (bounded: one call per horizon for h=1..3,
  // scored as of the SELECTED ORIGIN's history)
  const [live, setLive] = useState<LiveState>({ status: "idle" });
  const [spikeDisabled, setSpikeDisabled] = useState(false);
  useEffect(() => {
    if (spike === 1 || spikeDisabled || !originBlk) {
      setLive({ status: "idle" });
      return;
    }
    let cancelled = false;
    setLive({ status: "loading" });
    const timer = window.setTimeout(() => {
      Promise.all(
        LIVE_HORIZONS.map((h) => forecastDemand(payload.project, series.series_id, deriveFeatures(originBlk, h, spike))),
      )
        .then((rs) => {
          if (cancelled) return;
          setLive({ status: "ok", values: rs.map((r) => r.forecast) });
        })
        .catch(() => {
          if (cancelled) return;
          // churn-scorer pattern: a serving failure disables the lever
          setLive({ status: "unavailable" });
          setSpikeDisabled(true);
          setControl("spike", 1);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series.series_id, origin, spike, spikeDisabled]);

  // --- KPIs at origin + horizon
  const stats = horizonStats(originBlk, model, horizon);
  const naiveStats = horizonStats(originBlk, "naive", horizon);
  const coverage = coverageNote(payload);
  const originMeta = payload.origins_meta.origins.find((o) => o.label === origin);
  const isFrozenOrigin = originMeta?.holdout === "test";

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="forecast-origin">
              Forecast origin
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="forecast-origin"
                  type="range"
                  className="wb-slider"
                  min={0}
                  max={2}
                  step={1}
                  value={ORIGIN_INDEX[origin]}
                  style={{ "--fill": `${(ORIGIN_INDEX[origin] / 2) * 100}%` } as CSSProperties}
                  onChange={(e) => setOrigin(ORIGIN_LABELS[Number(e.target.value)])}
                />
                <span className="chip wb-value-badge">
                  {origin} · {fmtDay(originBlk?.origin_date ?? "")}
                  {originPct !== null && ` · ${originPct}% through history`}
                </span>
              </div>
              <div className="wb-origin-stops">
                {ORIGIN_LABELS.map((l) => (
                  <span key={l} className={`wb-origin-stop ${l === origin ? "active" : ""}`}>
                    {l}
                    {l === "test" && <span className="chip wb-origin-holdout">frozen test window</span>}
                  </span>
                ))}
              </div>
              <p className="demo-hint">
                pretend today is {fmtDay(originBlk?.origin_date ?? "")} — the explorer refits to what
                was known then
                {isFrozenOrigin && "; this origin is the holdout the models were never selected on"}
              </p>
            </div>
          </div>
          <div className="wb-control-group wb-group-presets">
            <span className="wb-rail-title" id="model-chips-label">
              Model
            </span>
            <div className="demo-control">
              <div className="demo-presets" role="group" aria-labelledby="model-chips-label">
                {MODELS.map((mk) => (
                  <button
                    key={mk}
                    type="button"
                    className={`chip demo-preset ${model === mk ? "active" : ""}`}
                    aria-pressed={model === mk}
                    onClick={() => setModel(mk)}
                  >
                    {mk}
                  </button>
                ))}
              </div>
              <p className="demo-hint">naive first — the floor every candidate must clear</p>
            </div>
          </div>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="forecast-horizon">
              Forecast horizon
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="forecast-horizon"
                  type="range"
                  className="wb-slider"
                  min={1}
                  max={payload.scalars.catalog_summary.horizon_days}
                  step={1}
                  value={horizon}
                  style={{ "--fill": `${((horizon - 1) / (payload.scalars.catalog_summary.horizon_days - 1)) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("horizon", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">{horizon}d</span>
              </div>
            </div>
          </div>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="demand-spike">
              Recent demand spike
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="demand-spike"
                  type="range"
                  className="wb-slider"
                  min={0.5}
                  max={1.5}
                  step={0.1}
                  value={spike}
                  disabled={spikeDisabled}
                  style={{ "--fill": `${((spike - 0.5) / 1) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("spike", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">×{spike.toFixed(1)}</span>
              </div>
              <p className="demo-hint">scales the lag features, re-scored live</p>
              {spikeDisabled && (
                <p className="state-box demo-score-note">
                  Live re-scoring unavailable — spike lever disabled, committed backtest shown
                </p>
              )}
            </div>
          </div>
          <div className="wb-control-group wb-group-picker">
            <span className="wb-rail-title" id="series-picker-label">
              Series catalog
            </span>
            <div className="demo-control">
              <input
                type="search"
                className="wb-series-search"
                placeholder="search store or product"
                aria-label="Search series"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <div className="demo-presets wb-class-filter" role="group" aria-label="Filter by demand class">
                {CLASSES.map((cls) => (
                  <button
                    key={cls}
                    type="button"
                    className={`chip demo-preset ${clsFilter === cls ? "active" : ""}`}
                    aria-pressed={clsFilter === cls}
                    onClick={() => setClsFilter(cls)}
                  >
                    {cls}
                  </button>
                ))}
              </div>
              <ul className="wb-series-list" aria-label="Series list" style={{ maxHeight: 340 }}>
                {filtered.map((s) => (
                  <li key={s.series_id}>
                    <button
                      type="button"
                      className={`wb-series-row ${s.series_id === series.series_id ? "active" : ""}`}
                      aria-pressed={s.series_id === series.series_id}
                      onClick={() => setSeriesId(s.series_id)}
                    >
                      <Sparkline
                        values={(originBlock(s, origin)?.history.y ?? []).slice(-30)}
                        color={MODEL_COLOR[model]}
                      />
                      <span className="wb-series-label">{s.label}</span>
                      <span className="chip wb-series-class">{s.demand_class}</span>
                    </button>
                  </li>
                ))}
                {filtered.length === 0 && <li className="wb-series-empty">no series matches</li>}
              </ul>
              <p className="demo-hint">
                {filtered.length} of {payload.catalog.length} series — sparklines show the{" "}
                {origin} origin's history
              </p>
            </div>
          </div>
        </>
      }
      canvas={
        <ExplorerPanel
          series={series}
          origin={origin}
          model={model}
          horizon={horizon}
          spike={spike}
          live={live}
          highlightDay={highlightDay}
        />
      }
      kpis={
        <>
          <KpiTile
            label="MASE at origin + horizon"
            value={
              stats?.mase == null
                ? "n/a"
                : `${stats.mase.toFixed(2)} vs ${naiveStats?.mase != null ? naiveStats.mase.toFixed(2) : "n/a"}`
            }
            sub={
              stats?.mase == null
                ? "(zero-scale window)"
                : `${model} vs seasonal-naive · ${fmtDay(originBlk?.origin_date ?? "")} + ${horizon}d`
            }
            tone={stats?.mase == null ? "neutral" : stats.mase < 1 ? "good" : "bad"}
          />
          <KpiTile
            label="Bias at origin + horizon"
            value={stats ? signed(stats.bias) : "n/a"}
            sub={
              stats
                ? `units · ${stats.bias > 0 ? "over-forecasts" : stats.bias < 0 ? "under-forecasts" : "unbiased"} · 1..${horizon}d`
                : "no committed curve"
            }
            tone={stats ? (stats.bias > 0 ? "bad" : stats.bias < 0 ? "good" : "neutral") : "neutral"}
          />
          <KpiTile
            label="WAPE at origin + horizon"
            value={stats?.wape == null ? "n/a" : `${(stats.wape * 100).toFixed(1)}%`}
            sub={`Σ|err| / Σ demand · 1..${horizon}d`}
          />
          <KpiTile
            label="Band coverage"
            value={coverage.value}
            sub={
              coverage.degenerate
                ? `${coverage.sub} — zero width on zero-demand days`
                : coverage.sub
            }
          />
        </>
      }
      notice={
        <>
          <Notice>
            <OriginContextText series={series} origin={origin} />
          </Notice>
          <Notice>
            <ModelVerdictText series={series} origin={origin} model={model} />
          </Notice>
        </>
      }
      secondary={
        <div className="wb-secondary-panel wb-secondary-wide">
          <div className="wb-tabs" role="tablist" aria-label="Secondary views">
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                className={`chip wb-tab ${tab === t ? "active" : ""}`}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="wb-tab-body">
            {tab === "model comparison" && (
              <ModelComparisonView series={series} model={model} onPickModel={setModel} />
            )}
            {tab === "error analysis" && (
              <ErrorAnalysisView
                series={series}
                origin={origin}
                model={model}
                highlightDay={highlightDay}
                onHighlight={setHighlightDay}
              />
            )}
            {tab === "uncertainty & reliability" && <UncertaintyView payload={payload} />}
          </div>
        </div>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">models used</h4>
            <p className="wb-evidence-line">
              <code className="wb-tag">{payload.scalars.models.champion}</code> — the committed
              backtest champion (one global pooled model;{" "}
              <code className="wb-tag">{payload.scalars.models.naive}</code> is the weekly floor,{" "}
              <code className="wb-tag">{payload.scalars.models.challenger}</code> the test-window
              runner-up).
            </p>
            <p className="wb-evidence-line">{payload.scalars.models.selection_rule}</p>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">{payload.evaluation_metadata.protocol}</span>
              <span className="wb-tag">
                {payload.evaluation_metadata.rolling_origin.n_origins} origins
              </span>
              <span className="wb-tag">
                {payload.evaluation_metadata.rolling_origin.origin_spacing_days}d spacing
              </span>
              <span className="wb-tag">
                horizon {payload.evaluation_metadata.rolling_origin.horizon_days}d
              </span>
              <span className="wb-tag">
                holdout: {payload.evaluation_metadata.holdout_designation}
              </span>
            </p>
            <p className="wb-evidence-line">
              Features: {payload.scalars.feature_schema.note} Calendar:{" "}
              {payload.scalars.feature_schema.calendar.join(", ")}; lags:{" "}
              {payload.scalars.feature_schema.lags.join(", ")}.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">metrics results</h4>
            <p className="wb-evidence-line">
              {payload.scalars.headline.claim.charAt(0).toUpperCase() +
                payload.scalars.headline.claim.slice(1)}
              .
            </p>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">
                champion {payload.scalars.headline.champion_mase.toFixed(3)} mase
              </span>
              <span className="wb-tag">
                {payload.scalars.headline.strongest_naive}{" "}
                {payload.scalars.headline.strongest_naive_mae.toFixed(2)} mae
              </span>
              <span className="wb-tag">
                {payload.scalars.headline.champion_mae_edge_vs_strongest_naive_pct}% vs floor
              </span>
              {Object.entries(payload.scalars.headline.mase_by_model)
                .sort((a, b) => a[1] - b[1])
                .map(([name, v]) => (
                  <span key={name} className="wb-tag">
                    {name} {v.toFixed(3)}
                  </span>
                ))}
            </p>
            {payload.scalars.band && (
              <p className="wb-evidence-line">
                Band: {(payload.scalars.band.quantile_coverage_pooled * 100).toFixed(1)}% pooled
                coverage (target {Math.round(payload.scalars.band.target_coverage * 100)}%),{" "}
                {payload.scalars.band.calibration_verdict ?? "uncommitted"} calibration —{" "}
                {payload.scalars.band.note}.
              </p>
            )}
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The workbench pretends today is a chosen point in history. The{" "}
              <strong>forecast origin</strong> slider moves that point across three committed
              rolling origins; the explorer shows only what was known as of that date — the origin's
              own 60-day history — plus the frozen 14-day window that came after, with every
              candidate model's backtest scored on it. The <strong>horizon</strong> slider stretches
              how much of the window is graded; the <strong>spike</strong> lever re-scores the first
              window days live through the served model.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              Daily demand for {payload.catalog.length} store-product series from the UCI Online
              Retail II track under the <strong>{payload.evaluation_metadata.protocol}</strong>{" "}
              protocol: {payload.evaluation_metadata.rolling_origin.n_origins} rolling origins,{" "}
              {payload.evaluation_metadata.rolling_origin.origin_spacing_days}-day spacing,{" "}
              {payload.evaluation_metadata.rolling_origin.horizon_days}-day horizon.{" "}
              {payload.evaluation_metadata.target_definition} Models were selected on origins{" "}
              {payload.evaluation_metadata.selection_used_origins.join(", ")} only; the final origin
              is a <strong>frozen test window</strong> scored once and never read for selection.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">honest limitation</h4>
            <p className="wb-evidence-line">
              {payload.scalars.headline.runs_below_mase_1.length === 0 && (
                <>
                  No run clears <span className="wb-tag">MASE 1</span> on the frozen test window —{" "}
                </>
              )}
              the committed band is degenerate on sparse demand (zero width on zero-demand days), so
              its headline coverage is conservative but uninformative where the point forecast
              matters least. {payload.dataset_metadata.zero_sales_caveat} Inventory planning would
              still need per-series safety-stock calibration, a trading calendar separating "closed"
              from "no demand", and a lead-time/service-level objective the demo does not commit.
            </p>
          </div>
        </>
      }
    />
  );
}
