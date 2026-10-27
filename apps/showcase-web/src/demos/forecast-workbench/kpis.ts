import type {
  BandsBlock,
  CatalogSeries,
  DecisionBlock,
  DemandClass,
  DirectModelBlock,
  ForecastPayload,
  HorizonGrowth,
  ModelKey,
  OriginBlock,
  RoutedMethod,
  ScoreboardClass,
} from "../types";

// --- calendar ----------------------------------------------------------------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2010-12-09" → local Date (midnight, no TZ shift). */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** The contiguous daily axis the explorer draws on: from the history's
 * first day through the last actual — the origin date sits in it as a real
 * slot (history ends the day before, actuals start the day after; there is
 * no gap to shade).
 *
 * Built with wall-calendar arithmetic (`addDays`), never by mutating a
 * local-time Date in a loop: a `new Date(iso)` loop drifts across DST
 * transitions (e.g. the CET fall-back inside these 2010 windows) and can
 * silently drop the final window day from the axis. */
export function windowAxis(origin: OriginBlock | null): string[] {
  if (!origin || origin.history.dates.length === 0 || origin.actuals.dates.length === 0) {
    return [];
  }
  const first = origin.history.dates[0];
  const last = origin.actuals.dates[origin.actuals.dates.length - 1];
  // both parse as UTC midnight, so the day count is exact
  const nDays = Math.round((Date.parse(last) - Date.parse(first)) / 86400000);
  return Array.from({ length: nDays + 1 }, (_, i) => addDays(first, i));
}

/** "2010-12-09" → "Dec 9". */
export function fmtDay(iso: string): string {
  const d = parseDay(iso);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

/** ISO date n days away ("2010-12-09", 1 → "2010-12-10"). */
export function addDays(iso: string, n: number): string {
  const d = parseDay(iso);
  d.setDate(d.getDate() + n);
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// --- origin + curve accessors --------------------------------------------------

/** Safe accessor: a series' origin block for one of the scored origin dates. */
export function originBlock(series: CatalogSeries, originDate: string): OriginBlock | null {
  return series.origins?.find((o) => o.origin_date === originDate) ?? null;
}

/** The scored origin dates (ascending) — the origin slider's stops. */
export function originDates(payload: ForecastPayload): string[] {
  return payload.catalog_summary.origins.map((o) => o.origin_date);
}

/** Short chip label for a committed routing method. */
const METHOD_SHORT: Record<RoutedMethod, string> = {
  direct_hgb: "boosted HGB",
  zero: "zero",
  seasonal_naive: "seasonal-naive",
  croston: "croston",
  sba: "sba",
  tsb: "tsb",
  ma_28: "ma_28",
  adida_sba: "adida_sba",
  adida_tsb: "adida_tsb",
  hurdle_hgb: "hurdle",
  hgb_tweedie: "tweedie",
  lgbm_tweedie: "lgbm_tweedie",
  lgbm_poisson: "lgbm_poisson",
  hurdle_lgbm: "hurdle_lgbm",
  peak_weighted_hgb: "peak-weighted",
};

/** The peak-capable candidate chips (wave 20) ↔ their payload block keys. */
export const CANDIDATE_METHOD = {
  hurdle: "hurdle_hgb",
  tweedie: "hgb_tweedie",
} as const;

/** Is the peak-capable candidate available for this series? Only where the
 * committed router selected it — the candidate curve IS the routed curve
 * there (payload revision 3.1 alias entries). */
export function candidateAvailable(
  series: CatalogSeries,
  m: keyof typeof CANDIDATE_METHOD,
): boolean {
  return series.model_used === CANDIDATE_METHOD[m];
}

/** A concrete curve block (alias markers resolved away by `modelBlock`). */
export type CurveBlock = DirectModelBlock;

/** Resolve a model chip to its curve block at an origin (`champion` →
 * `champion_hgb`; candidate chips → their alias-resolved block; `adida` →
 * the y_pred-only wave-22 block, wrapped with an EMPTY shock grid so
 * `curveAt` falls back to the base curve under an active shock — the
 * workbench shows the base curve with a note, never a fabricated shock). */
export function modelBlock(origin: OriginBlock | null, model: ModelKey): CurveBlock | null {
  if (!origin) return null;
  if (model === "champion") return origin.models.champion_hgb ?? null;
  if (model === "hurdle" || model === "tweedie") {
    const blk = origin.models[CANDIDATE_METHOD[model]];
    if (!blk) return null;
    return "alias" in blk ? modelBlock(origin, "routed") : blk;
  }
  if (model === "adida") {
    const blk = origin.models.adida;
    return blk ? { y_pred: blk.y_pred, shock: {} } : null;
  }
  return origin.models[model];
}

/** The model curve under the demand-shock lever: shock 1 is the committed
 * base curve; other stops read the precomputed exact re-scores. */
export function curveAt(block: CurveBlock | null, shock: number): number[] {
  if (!block) return [];
  if (shock === 1) return block.y_pred;
  const hit = block.shock[String(shock)];
  return hit ?? block.y_pred;
}

/** The plotted daily path of a model curve: one {date, y} per horizon h,
 * mapped onto the window actuals' dates (day origin+h). With the committed
 * full h = 1..14 lattice this covers the WHOLE window — 14 contiguous days,
 * no gaps, every point a real direct-h model. Null-safe. */
export function plottedPath(
  origin: OriginBlock | null,
  model: ModelKey,
  shock: number,
): Array<{ date: string; y: number }> {
  if (!origin) return [];
  const pred = curveAt(modelBlock(origin, model), shock);
  const out: Array<{ date: string; y: number }> = [];
  for (let i = 0; i < origin.horizons.length; i++) {
    const dayIdx = origin.horizons[i] - 1; // actuals are the 14 days after the origin
    if (origin.actuals.y[dayIdx] === undefined || pred[i] === undefined) continue;
    out.push({ date: origin.actuals.dates[dayIdx], y: pred[i] });
  }
  return out;
}

/** Chip label for the routed model, per-series honest: the committed method. */
export function routedLabel(series: CatalogSeries): string {
  return `routed · ${METHOD_SHORT[series.model_used]}`;
}

// --- KPIs at (origin, h) -------------------------------------------------------

export interface HorizonKpi {
  /** |err| of the direct h-step forecast (the day-h point of the curve). */
  mae: number;
  /** |err| over the origin history's seasonal-naive scale; null on zero scale. */
  mase: number | null;
  /** Signed error (pred − actual) of the day-h point. */
  bias: number;
  /** |err| / |actual| of the day-h point; null on zero demand that day. */
  wape: number | null;
  /** The day-h signed error. */
  signed: number;
  /** The day-h |err|. */
  abs: number;
}

/** Per-lattice signed errors of a model curve vs the window actuals: index i
 * is the error of the direct h-step forecast for h = horizons[i], evaluated
 * against the actual of day origin+h. Null-safe, never NaN. */
export function latticeErrors(
  origin: OriginBlock | null,
  model: ModelKey,
  shock: number,
): Array<{ h: number; signed: number; abs: number; over: boolean; date: string }> {
  if (!origin) return [];
  const block = modelBlock(origin, model);
  const pred = curveAt(block, shock);
  const out: Array<{ h: number; signed: number; abs: number; over: boolean; date: string }> = [];
  for (let i = 0; i < origin.horizons.length; i++) {
    const dayIdx = origin.horizons[i] - 1; // actuals are the 14 days after the origin
    const actual = origin.actuals.y[dayIdx];
    if (actual === undefined || pred[i] === undefined) continue;
    const signed = pred[i] - actual;
    out.push({
      h: origin.horizons[i],
      signed,
      abs: Math.abs(signed),
      over: signed > 0,
      date: origin.actuals.dates[dayIdx],
    });
  }
  return out;
}

/** KPI band for one model at (origin, h), taken AT exactly h: with the full
 * h = 1..14 lattice every horizon is a real direct model, so the graded cell
 * is the single day-h point — sliding h genuinely changes every number. Null
 * when h is off the curve or the origin is missing. */
export function horizonKpi(
  origin: OriginBlock | null,
  model: ModelKey,
  shock: number,
  h: number,
): HorizonKpi | null {
  const errs = latticeErrors(origin, model, shock);
  const dayH = errs.find((e) => e.h === h);
  if (!origin || !dayH) return null;
  const scale = origin.scale ?? 0;
  const actual = origin.actuals.y[h - 1];
  return {
    mae: dayH.abs,
    mase: scale > 0 ? dayH.abs / scale : null,
    bias: dayH.signed,
    wape: actual !== 0 ? dayH.abs / Math.abs(actual) : null,
    signed: dayH.signed,
    abs: dayH.abs,
  };
}

/** Percent by which `winner` beats the `floor` on a lower-is-better metric:
 * (floor − winner) / floor × 100. Null when the floor is 0 or either side is
 * missing — callers degrade to prose without a number. */
export function pctEdge(winner: number | null | undefined, floor: number | null | undefined): number | null {
  if (winner == null || floor == null || !(floor > 0)) return null;
  return ((floor - winner) / floor) * 100;
}

// --- horizon growth ------------------------------------------------------------

/** Pooled MAE of a candidate at one true horizon (from the committed growth
 * curves); null when the horizon is off the committed lattice. */
export function growthAt(
  growth: HorizonGrowth,
  series: "routed" | "seasonal_naive" | "zero",
  h: number,
): number | null {
  const v = growth.pooled[series]?.[String(h)];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Pooled MASE at one true horizon (champion or floor). */
export function growthMaseAt(growth: HorizonGrowth, policy: "champion" | "floor", h: number): number | null {
  const v = growth.mase[policy]?.[String(h)];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** The horizon-truth ratio for the notice tile: how many times larger the
 * error is at hFar than at hNear (derived, never hardcoded). */
export function growthRatio(growth: HorizonGrowth, hFar: number, hNear: number): number | null {
  const far = growthMaseAt(growth, "champion", hFar) ?? growthAt(growth, "routed", hFar);
  const near = growthMaseAt(growth, "champion", hNear) ?? growthAt(growth, "routed", hNear);
  if (far === null || near === null || !(near > 0)) return null;
  return far / near;
}

// --- class scoreboard ----------------------------------------------------------

/** One class × horizon scoreboard row, flattened for the table. */
export interface ScoreboardRow {
  cls: DemandClass;
  h: number;
  nSeries: number;
  beatsCount: number | null;
  beatsShare: number | null;
  modelMae: number | null;
  floorMae: number | null;
  gap: { diff: number; ci95: [number, number]; spansZero: boolean } | null;
  vsZero: { diff: number; ci95: [number, number]; spansZero: boolean } | null;
}

/** The h-keyed row of one class' scoreboard (h = 7 or 14 where committed). */
export function scoreboardRow(
  scoreboard: Record<DemandClass, ScoreboardClass>,
  cls: DemandClass,
  h: number,
): ScoreboardRow {
  const board = scoreboard[cls];
  const key = `h${h}`;
  const beats = board?.beats_floor?.[key];
  const mae = board?.mae?.[key];
  const gap = board?.gap_bootstrap?.[key];
  const vsZero = board?.vs_zero_bootstrap?.[key];
  return {
    cls,
    h,
    nSeries: board?.n_series ?? 0,
    beatsCount: beats?.count ?? null,
    beatsShare: beats?.share ?? null,
    modelMae: mae?.model ?? null,
    floorMae: mae?.floor ?? null,
    gap: gap ? { diff: gap.diff, ci95: gap.ci95, spansZero: gap.spans_zero } : null,
    vsZero: vsZero ? { diff: vsZero.diff, ci95: vsZero.ci95, spansZero: vsZero.spans_zero } : null,
  };
}

// --- bands ---------------------------------------------------------------------

/** Per-h committed coverage/width/verdict; null off the lattice. */
export function bandAt(bands: BandsBlock | null, h: number): {
  coverage: number;
  avgWidth: number;
  verdict: string;
} | null {
  const row = bands?.per_horizon?.[String(h)];
  if (!row) return null;
  return { coverage: row.coverage, avgWidth: row.avg_width, verdict: row.calibration_verdict };
}

// --- decision layer ------------------------------------------------------------

/** Order-up-to quantity: the committed τ→quantile mapping applied to a point
 * forecast — order = max(point + offset, 0). */
export function orderQuantity(point: number, offset: number): number {
  return Math.max(point + offset, 0);
}

/** Per-h order quantities for one policy at the selected τ: the series'
 * point curve + the class offset (the committed simulation's mapping). */
export function orderPolicy(
  decision: DecisionBlock,
  cls: DemandClass,
  policy: "champion" | "floor",
  pointCurve: number[],
  horizons: number[],
  tau: number,
): number[] {
  const tauKey = tau.toFixed(2);
  return horizons.map((h, i) => {
    const offset = decision.quantile_map?.[cls]?.[policy]?.[String(h)]?.[tauKey];
    return orderQuantity(pointCurve[i] ?? 0, typeof offset === "number" ? offset : 0);
  });
}

/** Over/under-stocked units + documented holding/stockout cost for one
 * policy's orders against the origin window's actuals at the lattice days. */
export function policyWindow(
  orders: number[],
  horizons: number[],
  actuals: { y: number[] },
  costs: { holding: number; stockout: number },
): { overUnits: number; underUnits: number; cost: number } {
  let overUnits = 0;
  let underUnits = 0;
  for (let i = 0; i < horizons.length; i++) {
    const actual = actuals.y[horizons[i] - 1] ?? 0;
    const order = orders[i] ?? 0;
    if (order > actual) overUnits += order - actual;
    else underUnits += actual - order;
  }
  return {
    overUnits,
    underUnits,
    cost: costs.holding * overUnits + costs.stockout * underUnits,
  };
}

// --- stratified surprise-me ------------------------------------------------------

/** Deterministic PRNG (mulberry32) — the surprise-me seed comes from the URL
 * so a pick is shareable and testable. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Class-stratified random pick over the filtered catalog: uniform over the
 * classes present, then uniform within the class — so surprise-me respects
 * the class mix (all 15 erratic series stand a 1/2 chance each draw, not
 * 15/100). */
export function surprisePick(catalog: CatalogSeries[], rng: () => number): CatalogSeries | null {
  if (catalog.length === 0) return null;
  const byClass = new Map<DemandClass, CatalogSeries[]>();
  for (const s of catalog) {
    const list = byClass.get(s.demand_class) ?? [];
    list.push(s);
    byClass.set(s.demand_class, list);
  }
  const classesArr = [...byClass.keys()];
  const cls = classesArr[Math.floor(rng() * classesArr.length)] ?? classesArr[0];
  const pool = byClass.get(cls) ?? catalog;
  return pool[Math.floor(rng() * pool.length)] ?? pool[0] ?? null;
}

/** Parse a non-negative integer from the URL (the surprise-me seed). */
export function seedFromQuery(): number | null {
  try {
    const raw = new URLSearchParams(window.location.search).get("seed");
    if (raw === null) return null;
    const v = Number(raw);
    return Number.isInteger(v) && v >= 0 ? v : null;
  } catch {
    return null;
  }
}
