import type { CatalogSeries, ForecastPayload } from "../types";

type SeriesErrors = CatalogSeries["errors"];
type Who = "champion" | "naive";

/** Champion MASE at horizon h (1-based); null when the series' seasonal
 * scale is 0 (all-zero sparse history) — callers render "n/a", never NaN. */
export function maseAt(errors: SeriesErrors | undefined | null, h: number, who: Who = "champion"): number | null {
  const arr = errors?.[who]?.mase;
  if (!arr || h < 1 || h > arr.length) return null;
  return arr[h - 1];
}

/** Absolute error at horizon h (1-based); null-safe like maseAt. */
export function maeAt(errors: SeriesErrors | undefined | null, h: number, who: Who = "champion"): number | null {
  const arr = errors?.[who]?.mae;
  if (!arr || h < 1 || h > arr.length) return null;
  return arr[h - 1];
}

/** Pooled window MASE: the mean of the non-null per-horizon entries (null
 * when every entry is null, i.e. a zero-scale sparse series). */
export function windowMase(errors: SeriesErrors | undefined | null, who: Who = "champion"): number | null {
  const arr = errors?.[who]?.mase;
  if (!arr) return null;
  const vals = arr.filter((v): v is number => v !== null);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** Coverage line for the band-coverage KPI, from the committed scalars. */
export function coverageNote(payload: ForecastPayload): { value: string; sub: string } {
  const band = payload.scalars.band;
  if (!band) return { value: "n/a", sub: "no probabilistic report committed" };
  return {
    value: `${(band.quantile_coverage_pooled * 100).toFixed(1)}%`,
    sub: `p10–p90 on backtest (target ${Math.round(band.target_coverage * 100)}%)`,
  };
}

/** Live-vs-committed spike reaction: signed delta and percent lift. */
export function spikeDelta(live: number, committed: number): { delta: number; pct: number } {
  const delta = live - committed;
  return { delta, pct: committed > 0 ? (delta / committed) * 100 : 0 };
}

/** Highest daily demand in the stored history and the date it happened. */
export function historyPeak(series: CatalogSeries): { value: number; date: string } | null {
  const { dates, y } = series.history;
  if (!y.length) return null;
  let best = 0;
  for (let i = 1; i < y.length; i++) {
    if (y[i] > y[best]) best = i;
  }
  return { value: y[best], date: dates[best] };
}

// --- calendar + live feature derivation -------------------------------------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2010-12-09" → local Date (midnight, no TZ shift). */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "2010-12-09" → "Dec 9". */
export function fmtDay(iso: string): string {
  const d = parseDay(iso);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

/** ISO-8601 week number (polars `dt.week()`), the model's `week` feature. */
export function isoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export const LIVE_HORIZONS = [1, 2, 3] as const;

/**
 * Feature row for the live what-if call at horizon h (1-based), mirroring
 * `demand_forecasting.features`: calendar features are deterministic
 * functions of the prediction date (last history date + h; polars weekday
 * 1=Mon..7=Sun, weekend = Sat/Sun, week = ISO week, doy_* = day-of-year
 * harmonics over 365.25), and each lag_k is the demand k days before the
 * prediction day — a committed history value, or the committed day-1
 * forecast when the lag day falls inside the window. The spike story:
 * the last week ran hot, so lag days within 7 days of the origin are
 * scaled by the spike factor; older lags stay committed.
 */
export function deriveFeatures(
  series: CatalogSeries,
  h: number,
  spike: number,
): Record<string, number> {
  const n = series.history.y.length;
  const day = parseDay(series.history.dates[n - 1]);
  day.setDate(day.getDate() + h);
  const dowJs = day.getDay(); // 0=Sun..6=Sat
  const dow = dowJs === 0 ? 7 : dowJs; // polars convention: 1=Mon..7=Sun
  const ordinal = Math.floor(
    (Date.UTC(day.getFullYear(), day.getMonth(), day.getDate()) -
      Date.UTC(day.getFullYear(), 0, 1)) / 86400000,
  ) + 1;
  const angle = (ordinal * Math.PI * 2) / 365.25;
  const lagValue = (k: number): number => {
    const idx = n - 1 + h - k;
    let v: number;
    if (idx < n) {
      v = series.history.y[idx];
    } else {
      v = series.forecast.y_pred[idx - n] ?? series.forecast.y_pred[series.forecast.y_pred.length - 1];
    }
    return h - k >= -6 ? v * spike : v;
  };
  return {
    t: n - 1 + h,
    dow,
    is_weekend: dow >= 6 ? 1 : 0,
    month: day.getMonth() + 1,
    week: isoWeek(day),
    doy_sin: Math.sin(angle),
    doy_cos: Math.cos(angle),
    lag_1: lagValue(1),
    lag_7: lagValue(7),
    lag_14: lagValue(14),
  };
}

// --- catalog-wide pools ------------------------------------------------------

/** Mean window MASE over the catalog series of one demand class; null-safe
 * per series (zero-scale sparse series are skipped, not counted as 0). */
export function classPooledMase(
  catalog: CatalogSeries[],
  cls: CatalogSeries["demand_class"],
  who: Who = "champion",
): number | null {
  const vals = catalog
    .filter((s) => s.demand_class === cls)
    .map((s) => windowMase(s.errors, who))
    .filter((v): v is number => v !== null);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** The first (highest-volume) catalog series of each demand class — the
 * class explorer's representatives. */
export function representativeByClass(
  catalog: CatalogSeries[],
): Record<CatalogSeries["demand_class"], CatalogSeries | undefined> {
  const out: Record<CatalogSeries["demand_class"], CatalogSeries | undefined> = {
    smooth: undefined,
    intermittent: undefined,
    sparse: undefined,
  };
  for (const cls of ["smooth", "intermittent", "sparse"] as const) {
    out[cls] = catalog.find((s) => s.demand_class === cls);
  }
  return out;
}
