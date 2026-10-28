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

/** MAE on the top-decile-by-actual days among the first `h` scored days
 * (the track's peak_mae rule, k = ceil(0.1·h) ≥ 1). */
export function peakDayMae(actual: number[], pred: number[], h: number): number {
  const n = Math.max(1, Math.min(h, actual.length));
  const idx = Array.from({ length: n }, (_, i) => i).sort((a, b) => actual[b] - actual[a]);
  const k = Math.max(1, Math.ceil(0.1 * n));
  let sum = 0;
  for (let i = 0; i < k; i++) {
    sum += Math.abs(pred[idx[i]] - actual[idx[i]]);
  }
  return sum / k;
}

/** Truncate the lgbm band to the first `h` days. */
export function bandAt(
  window: ForecastWindow,
  h: number,
): { p10: number[]; p90: number[] } {
  const n = Math.max(0, Math.min(h, window.actual.length));
  return { p10: window.band.p10.slice(0, n), p90: window.band.p90.slice(0, n) };
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

/** Band calibration over the first `h` scored days, straight from the payload
 * arrays: per-day hit indicator (p10 ≤ actual ≤ p90), the coverage fraction
 * and the mean p10→p90 width. NaN-safe when the band is missing. */
export function bandCalibration(
  window: ForecastWindow,
  h: number,
): { hits: number; n: number; coverage: number; meanWidth: number } {
  const n = Math.max(0, Math.min(h, window.actual.length, window.band.p10.length, window.band.p90.length));
  let hits = 0;
  let width = 0;
  for (let i = 0; i < n; i++) {
    const lo = window.band.p10[i];
    const hi = window.band.p90[i];
    if (window.actual[i] >= lo && window.actual[i] <= hi) hits += 1;
    width += hi - lo;
  }
  return { hits, n, coverage: n > 0 ? hits / n : 0, meanWidth: n > 0 ? width / n : 0 };
}

/** Per-day p10→p90 band width over the first `h` scored days — the width
 * trajectory behind the calibration sparkline (uncertainty vs horizon). */
export function bandWidthTrajectory(window: ForecastWindow, h: number): number[] {
  const n = Math.max(0, Math.min(h, window.actual.length, window.band.p10.length, window.band.p90.length));
  return Array.from({ length: n }, (_, i) => window.band.p90[i] - window.band.p10[i]);
}

/** Coverage (fraction of days inside p10/p90) per 7-day bucket over the first
 * `h` scored days: ceil(h/7) entries, one per non-empty week — shows where
 * calibration drifts across the window. */
export function weeklyBandCoverage(window: ForecastWindow, h: number): number[] {
  const n = Math.max(0, Math.min(h, window.actual.length, window.band.p10.length, window.band.p90.length));
  const hits: number[] = [];
  const counts: number[] = [];
  for (let i = 0; i < n; i++) {
    const w = Math.floor(i / 7);
    counts[w] = (counts[w] ?? 0) + 1;
    if (window.actual[i] >= window.band.p10[i] && window.actual[i] <= window.band.p90[i]) {
      hits[w] = (hits[w] ?? 0) + 1;
    }
  }
  return counts.map((c, w) => (hits[w] ?? 0) / c);
}

/** The single worst band violation over the first `h` scored days — the day
 * furthest outside p10/p90, which side it left through, and by how much.
 * Null when every scored day is inside the band. */
export function worstBandMiss(
  window: ForecastWindow,
  h: number,
): { day: number; side: "over" | "under"; actual: number; bound: number; amount: number } | null {
  const n = Math.max(0, Math.min(h, window.actual.length, window.band.p10.length, window.band.p90.length));
  let worst: { day: number; side: "over" | "under"; actual: number; bound: number; amount: number } | null = null;
  for (let i = 0; i < n; i++) {
    const over = window.actual[i] - window.band.p90[i];
    const under = window.band.p10[i] - window.actual[i];
    const amount = Math.max(over, under);
    if (amount > 0 && (worst === null || amount > worst.amount)) {
      worst =
        over >= under
          ? { day: i, side: "over", actual: window.actual[i], bound: window.band.p90[i], amount }
          : { day: i, side: "under", actual: window.actual[i], bound: window.band.p10[i], amount };
    }
  }
  return worst;
}

/** Sum of |pred − actual| grouped into `buckets` equal spans across the first
 * `h` scored days — the row-level error *shape* behind the verdict micro-bars,
 * comparable across models regardless of window length. */
export function bucketedAbsError(actual: number[], pred: number[], h: number, buckets = 7): number[] {
  const n = Math.max(0, Math.min(h, actual.length));
  const out = Array<number>(buckets).fill(0);
  if (n === 0) return out;
  for (let i = 0; i < n; i++) {
    const b = Math.min(buckets - 1, Math.floor((i / n) * buckets));
    out[b] += Math.abs(pred[i] - actual[i]);
  }
  return out;
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

/** Per-weekday totals of |pred − actual| over the first `h` scored days,
 * bucketed Mon..Sun by the forecast dates (index 0 = Mon). Days whose date is
 * missing or unparseable are skipped; entries with no scored day stay 0. */
export function weekdayAbsError(actual: number[], pred: number[], dates: string[], h: number): number[] {
  const n = Math.max(0, Math.min(h, actual.length, dates.length));
  const out = Array<number>(7).fill(0);
  for (let i = 0; i < n; i++) {
    const dow = new Date(`${dates[i]}T00:00:00Z`).getUTCDay();
    if (!Number.isFinite(dow)) continue;
    out[(dow + 6) % 7] += Math.abs(pred[i] - actual[i]);
  }
  return out;
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
