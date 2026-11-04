import type { ForecastWindow } from "../types";

/** Pooled WAPE over the first `h` days: Σ|err| / Σ actual (NaN-safe → 0 when
 * the scored volume is 0). */
export function wapeAt(actual: number[], pred: number[], h: number): number {
  const n = Math.max(0, Math.min(h, actual.length));
  let err = 0;
  let vol = 0;
  for (let i = 0; i < n; i++) {
    err += Math.abs(pred[i] - actual[i]);
    vol += actual[i];
  }
  return vol > 0 ? err / vol : 0;
}

/** The best (lowest WAPE@h) candidate among the selected models — the KPI
 * headline. `seasonal_naive` is the floor, never the "best" unless it is the
 * only selection. */
export function bestModelAt(
  window: ForecastWindow,
  models: string[],
  h: number,
): string | null {
  const candidates = models.filter((m) => m !== "seasonal_naive" && window.curves[m]);
  const pool = candidates.length > 0 ? candidates : models.filter((m) => window.curves[m]);
  let best: string | null = null;
  for (const m of pool) {
    if (best === null || wapeAt(window.actual, window.curves[m], h) < wapeAt(window.actual, window.curves[best], h)) {
      best = m;
    }
  }
  return best;
}

/** Sum of |pred − actual| grouped into 7-day week buckets over the first `h`
 * scored days: ceil(h/7) buckets — the 4-bar view at the full 28-day window,
 * fewer bars as the horizon toggle shortens the scored window. */
export function weeklyAbsError(actual: number[], pred: number[], h: number): number[] {
  const n = Math.max(0, Math.min(h, actual.length));
  const buckets: number[] = [];
  for (let i = 0; i < n; i++) {
    const w = Math.floor(i / 7);
    buckets[w] = (buckets[w] ?? 0) + Math.abs(pred[i] - actual[i]);
  }
  return buckets;
}

/** Worst single-day |pred − actual| over the first `h` scored days — the
 * per-model peak-day MAE quoted in the verdict rows. */
export function peakAbsError(actual: number[], pred: number[], h: number): number {
  const n = Math.max(0, Math.min(h, actual.length));
  let peak = 0;
  for (let i = 0; i < n; i++) {
    peak = Math.max(peak, Math.abs(pred[i] - actual[i]));
  }
  return peak;
}

/** One-line per-series verdict for the notice strip. */
export function verdictText(
  window: ForecastWindow,
  model: string | null,
  h: number,
): string {
  if (!model || !window.curves[model]) {
    return "Select a model to compare against the seasonal-naive floor.";
  }
  const modelWape = wapeAt(window.actual, window.curves[model], h);
  const naiveWape = wapeAt(window.actual, window.curves.seasonal_naive, h);
  const delta = modelWape - naiveWape;
  const pct = naiveWape > 0 ? Math.abs((delta / naiveWape) * 100) : 0;
  if (Math.abs(delta) < 1e-9) {
    return `At h = ${h} this model ties the seasonal-naive floor on the scored window.`;
  }
  return delta < 0
    ? `At h = ${h} this model beats the seasonal naive by ${pct.toFixed(1)}% WAPE on this series — the pooled committed gap is what generalises.`
    : `At h = ${h} the seasonal naive still wins this series by ${pct.toFixed(1)}% WAPE — per-series losses are real even when the pooled gap excludes zero.`;
}
