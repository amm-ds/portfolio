import type { LineSeries } from "../charts/LineChart";
import type { ForecastWindow } from "../types";

export const C_TEAL = "#2dd4bf";
export const C_TEAL_LIGHT = "#5eead4";
export const C_PINK = "#f472b6";
export const C_AMBER = "#fbbf24";
export const C_GRAY = "#64748b";
export const C_LILAC = "#a78bfa";
export const C_VIOLET = "#7c3aed";
export const C_SKY = "#38bdf8";
export const C_GREEN = "#4ade80";
export const C_HIST = "#94a3b8";

/** The 8 full-panel candidates: naive dashed grey, AutoETS thin, the global
 * LightGBM arms in teal hues, the three pooled fits in cool distinct hues,
 * and the screened ensemble bold amber. */
export const MODELS: {
  key: string;
  label: string;
  color: string;
  width: number;
  dashed?: boolean;
  tooltip?: string;
}[] = [
  { key: "seasonal_naive", label: "seasonal naive", color: C_GRAY, width: 2, dashed: true },
  { key: "auto_ets", label: "AutoETS", color: C_LILAC, width: 1.5 },
  { key: "lgbm", label: "LightGBM", color: C_TEAL, width: 2 },
  {
    key: "lgbm_tweedie",
    label: "LightGBM tweedie",
    color: C_VIOLET,
    width: 1.5,
    tooltip: "same global pipeline, Tweedie loss (variance power 1.1)",
  },
  {
    key: "lgbm_pool_store",
    label: "pooled store",
    color: C_SKY,
    width: 2,
    tooltip: "one LightGBM fit per store (10 groups)",
  },
  {
    key: "lgbm_pool_storecat",
    label: "pooled store×cat",
    color: C_TEAL_LIGHT,
    width: 2,
    tooltip: "one LightGBM fit per store×category cell (30 groups)",
  },
  {
    key: "lgbm_pool_dept",
    label: "pooled dept",
    color: C_GREEN,
    width: 2,
    tooltip: "one LightGBM fit per department (7 groups)",
  },
  { key: "convex_ensemble", label: "ensemble", color: C_AMBER, width: 3 },
];

export interface ForecastChartSpec {
  /** Day-index axis: d-(historyDays-1) .. 0 (history) then +1 .. +28 (window). */
  x: number[];
  series: LineSeries[];
  /** Indices into `series` of the [lo, hi] envelope edges, null when the
   * ensemble is off. */
  band: [number, number] | null;
  /** Clipped domain ceiling: the visible window only, so curves never go flat. */
  yMax: number;
  /** Number of forecast-window points actually plotted (the horizon clamp). */
  take: number;
}

/**
 * Assemble the LineChart payload for one (series × horizon × models)
 * selection. Pure and total: every returned series array is exactly
 * `x.length` long (gaps are explicit NaNs, never undefined), the band indices
 * always point at the two edge series when present, and `yMax` is finite.
 *
 * Layout: the history tail occupies x-axis slots 0..historyDays-1
 * (d-(historyDays-1)..0); the scored window occupies the trailing slots
 * (+1..+take). Forecast curves and the envelope are NaN in the history slots
 * and beyond `take`, so the chart draws them as isolated runs.
 */
export function assembleChartData(
  window: ForecastWindow,
  modelsOn: string[],
  h: number,
): ForecastChartSpec {
  const historyDays = window.history.length;
  const horizon = window.actual.length;
  const take = Math.max(0, Math.min(h, horizon));
  const n = historyDays + horizon;
  const x = Array.from({ length: n }, (_, i) => i - (historyDays - 1));
  const prefix: number[] = Array.from({ length: historyDays }, () => NaN);
  const suffix = (values: number[], keep: number): number[] =>
    prefix
      .concat(values.slice(0, keep))
      .concat(Array<number>(horizon - keep).fill(NaN));

  const series: LineSeries[] = [
    {
      name: "history",
      color: C_HIST,
      width: 1.5,
      opacity: 0.85,
      values: window.history.concat(Array<number>(horizon).fill(NaN)),
    },
    { name: "actual", color: C_PINK, width: 2.5, values: suffix(window.actual, horizon) },
  ];
  for (const m of MODELS) {
    if (modelsOn.includes(m.key) && window.curves[m.key]) {
      series.push({
        name: m.key,
        color: m.color,
        width: m.width,
        dashed: m.dashed,
        values: suffix(window.curves[m.key], take),
      });
    }
  }
  let band: [number, number] | null = null;
  if (
    modelsOn.includes("convex_ensemble") &&
    window.band.lo.length >= take &&
    window.band.hi.length >= take
  ) {
    band = [series.length, series.length + 1];
    series.push({ name: "envelope lo", color: "transparent", width: 1, values: suffix(window.band.lo, take) });
    series.push({ name: "envelope hi", color: "transparent", width: 1, values: suffix(window.band.hi, take) });
  }

  // clipped domain: history tail + the visible window only
  let max = 1;
  const grow = (v: number | undefined) => {
    if (typeof v === "number" && Number.isFinite(v) && v > max) max = v;
  };
  for (const v of window.history) grow(v);
  window.actual.slice(0, take).forEach(grow);
  for (const m of modelsOn) {
    const curve = window.curves[m];
    if (!curve) continue;
    for (let i = 0; i < take; i++) grow(curve[i]);
  }
  if (band) {
    for (let i = 0; i < take; i++) grow(window.band.hi[i]);
  }

  return { x, series, band, yMax: max * 1.08, take };
}
