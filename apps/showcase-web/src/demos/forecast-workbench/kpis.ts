import type {
  CatalogSeries,
  ForecastPayload,
  ModelKey,
  OriginBlock,
  OriginLabel,
  OriginWindowMetrics,
} from "../types";

export const ORIGIN_LABELS: OriginLabel[] = ["early", "middle", "test"];

/** Slider stop index per origin label (the origin slider is 0..2). */
export const ORIGIN_INDEX: Record<OriginLabel, number> = { early: 0, middle: 1, test: 2 };

/** Safe accessor: a series' origin block, or null on a malformed entry. */
export function originBlock(series: CatalogSeries, origin: OriginLabel): OriginBlock | null {
  return series.origins?.[origin] ?? null;
}

/** The committed 14-day window metrics for one model at one origin. */
export function windowMetrics(
  origin: OriginBlock | null,
  model: ModelKey,
): OriginWindowMetrics | null {
  const m = origin?.models?.[model];
  if (!m || typeof m.mae !== "number") return null;
  return { mae: m.mae, mase: m.mase, bias: m.bias, wape: m.wape };
}

export interface HorizonStats {
  /** |err| on day h (1-based). */
  mae: number;
  /** Day-h |err| over the origin's seasonal-naive scale; null on zero scale. */
  mase: number | null;
  /** Mean signed error (pred − actual) over days 1..h. */
  bias: number;
  /** Σ|err| / Σ|actual| over days 1..h; null when the window demand is 0. */
  wape: number | null;
  /** The day-h signed error (pred − actual). */
  signed: number;
}

/** Per-horizon metrics at origin+horizon for one model, derived client-side
 * from the committed curve vs the origin's actuals — the payload stores the
 * curves rounded to 4 decimals, so this reproduces the committed window
 * metrics bit for bit when h = 14. Null-safe: a misaligned or missing block
 * yields null, never NaN. */
export function horizonStats(
  origin: OriginBlock | null,
  model: ModelKey,
  h: number,
): HorizonStats | null {
  const m = origin?.models?.[model];
  const pred = m?.y_pred;
  const actual = origin?.actuals?.y;
  if (!pred || !actual || pred.length !== actual.length) return null;
  if (h < 1 || h > pred.length) return null;
  let absErr = 0;
  let signedSum = 0;
  let absSum = 0;
  let actSum = 0;
  for (let i = 0; i < h; i++) {
    const e = pred[i] - actual[i];
    absErr += Math.abs(e);
    signedSum += e;
    absSum += Math.abs(e);
    actSum += Math.abs(actual[i]);
  }
  const dayErr = pred[h - 1] - actual[h - 1];
  const scale = origin?.scale ?? 0;
  return {
    mae: Math.abs(dayErr),
    mase: scale > 0 ? Math.abs(dayErr) / scale : null,
    bias: signedSum / h,
    wape: actSum > 0 ? absSum / actSum : null,
    signed: dayErr,
  };
}

/** Per-horizon-day signed errors for the error-analysis view. */
export interface DayError {
  /** 1-based horizon day. */
  h: number;
  signed: number;
  abs: number;
  /** True when the model over-forecasts that day (pred > actual). */
  over: boolean;
}

export function dayErrors(origin: OriginBlock | null, model: ModelKey): DayError[] {
  const pred = origin?.models?.[model]?.y_pred;
  const actual = origin?.actuals?.y;
  if (!pred || !actual || pred.length !== actual.length) return [];
  return pred.map((p, i) => {
    const signed = p - actual[i];
    return { h: i + 1, signed, abs: Math.abs(signed), over: signed > 0 };
  });
}

/** Percent by which `winner` beats the `floor` on a lower-is-better metric:
 * (floor − winner) / floor × 100. Null when the floor is 0 or either side is
 * missing — callers degrade to prose without a number. */
export function pctEdge(winner: number | null | undefined, floor: number | null | undefined): number | null {
  if (winner == null || floor == null || !(floor > 0)) return null;
  return ((floor - winner) / floor) * 100;
}

/** Coverage line for the band-coverage KPI, from the committed scalars. */
export function coverageNote(payload: ForecastPayload): {
  value: string;
  sub: string;
  /** True when the committed width curve is all-zero (degenerate band). */
  degenerate: boolean;
} {
  const band = payload.scalars.band;
  if (!band) return { value: "n/a", sub: "no probabilistic report committed", degenerate: false };
  const degenerate = band.horizon_avg_width.every((w) => w <= 0);
  return {
    value: `${(band.quantile_coverage_pooled * 100).toFixed(1)}%`,
    sub: `p10–p90 empirical (target ${Math.round(band.target_coverage * 100)}%)${
      degenerate ? " · degenerate width" : ""
    }`,
    degenerate,
  };
}

/** Live-vs-committed spike reaction: signed delta and percent lift. */
export function spikeDelta(live: number, committed: number): { delta: number; pct: number } {
  const delta = live - committed;
  return { delta, pct: committed > 0 ? (delta / committed) * 100 : 0 };
}

/** How far through the observed panel an origin date sits (0–100) — the
 * origin slider's "% through history" badge. Null without a date range. */
export function originPctThroughHistory(payload: ForecastPayload, origin: OriginLabel): number | null {
  const meta = payload.origins_meta?.origins?.find((o) => o.label === origin);
  const panel = payload.dataset_metadata?.observed_panel;
  if (!meta || !panel?.date_start || !panel?.date_end) return null;
  const start = parseDay(panel.date_start).getTime();
  const end = parseDay(panel.date_end).getTime();
  if (!(end > start)) return null;
  const at = parseDay(meta.origin_date).getTime();
  return Math.round(((at - start) / (end - start)) * 100);
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
 * functions of the prediction date (the origin date + h; polars weekday
 * 1=Mon..7=Sun, weekend = Sat/Sun, week = ISO week, doy_* = day-of-year
 * harmonics over 365.25), and each lag_k is the demand k days before the
 * prediction day — a committed as-of-origin history value, or the committed
 * day-1 forecast when the lag day falls inside the horizon window. The spike
 * story: the last week ran hot, so lag days within 7 days of the origin are
 * scaled by the spike factor; older lags stay committed.
 */
export function deriveFeatures(
  origin: OriginBlock,
  h: number,
  spike: number,
): Record<string, number> {
  const dates = origin.history.dates;
  const y = origin.history.y;
  const n = y.length;
  const day = parseDay(dates[n - 1]);
  day.setDate(day.getDate() + h);
  const dowJs = day.getDay(); // 0=Sun..6=Sat
  const dow = dowJs === 0 ? 7 : dowJs; // polars convention: 1=Mon..7=Sun
  const ordinal =
    Math.floor(
      (Date.UTC(day.getFullYear(), day.getMonth(), day.getDate()) -
        Date.UTC(day.getFullYear(), 0, 1)) / 86400000,
    ) + 1;
  const angle = (ordinal * Math.PI * 2) / 365.25;
  const lagValue = (k: number): number => {
    const idx = n - 1 + h - k;
    let v: number;
    if (idx < n) {
      v = y[idx];
    } else {
      const fc = origin.models.champion.y_pred;
      v = fc[idx - n] ?? fc[fc.length - 1];
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
