import type { LineSeries } from "../charts/LineChart";
import type { CatalogEntry, ForecastWindow } from "../types";

export const C_TEAL = "#2dd4bf";
export const C_TEAL_LIGHT = "#5eead4";
export const C_PINK = "#f472b6";
export const C_AMBER = "#fbbf24";
export const C_GRAY = "#64748b";
export const C_LILAC = "#a78bfa";
export const C_VIOLET = "#7c3aed";
export const C_HIST = "#94a3b8";

/** Demo candidates: naive dashed grey, AutoETS thin, lgbm accent, ensemble
 * bold; the wave-28 L2 arms get distinct-but-related hues (lighter teal,
 * deep violet) so the near-duplicate curves stay tellable apart. */
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
    key: "lgbm_l2",
    label: "lgbm l2",
    color: C_TEAL_LIGHT,
    width: 1.5,
    tooltip: "same booster, L2-selected blend — the wave-28 L1/L2 comparison",
  },
  { key: "convex_ensemble", label: "ensemble", color: C_AMBER, width: 3 },
  {
    key: "ensemble_l2",
    label: "ensemble l2",
    color: C_VIOLET,
    width: 2.5,
    tooltip: "same booster, L2-selected blend — the wave-28 L1/L2 comparison",
  },
];

export interface ForecastChartSpec {
  /** Day-index axis: d-(historyDays-1) .. 0 (history) then +1 .. +28 (window). */
  x: number[];
  series: LineSeries[];
  /** Indices into `series` of the [p10, p90] band edges, null when lgbm is off. */
  band: [number, number] | null;
  /** Clipped domain ceiling: the visible window only, so curves never go flat. */
  yMax: number;
  /** Number of forecast-window points actually plotted (the horizon clamp). */
  take: number;
}

/**
 * Assemble the LineChart payload for one (series × origin × horizon × models)
 * selection. Pure and total: every returned series array is exactly
 * `x.length` long (gaps are explicit NaNs, never undefined), the band indices
 * always point at the two edge series when present, and `yMax` is finite.
 *
 * Layout: the history tail occupies x-axis slots 0..historyDays-1
 * (d-(historyDays-1)..0); the scored window occupies the trailing slots
 * (+1..+take). Forecast curves and the band are NaN in the history slots and
 * beyond `take`, so the chart draws them as isolated runs.
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
  if (modelsOn.includes("lgbm") && window.band.p10.length >= take && window.band.p90.length >= take) {
    band = [series.length, series.length + 1];
    series.push({ name: "p10", color: "transparent", width: 1, values: suffix(window.band.p10, take) });
    series.push({ name: "p90", color: "transparent", width: 1, values: suffix(window.band.p90, take) });
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
    for (let i = 0; i < take; i++) grow(window.band.p90[i]);
  }

  return { x, series, band, yMax: max * 1.08, take };
}

/** Type helper for the component: the per-origin window map of a catalog entry. */
export type OriginWindow = CatalogEntry["origins"][string];
