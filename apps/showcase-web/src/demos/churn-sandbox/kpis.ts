import type { ConfusionRow } from "../types";

/** A zeroed row for out-of-range cursor indices / undefined rows: every kpi
 * function must degrade to safe values instead of throwing mid-drag. */
const ZERO_ROW: ConfusionRow = { t: 0, tn: 0, fp: 0, fn: 0, tp: 0 };

function safeRow(row: ConfusionRow | undefined | null): ConfusionRow {
  return row ?? ZERO_ROW;
}

function safeRatio(fnRatio: number): number {
  return Number.isFinite(fnRatio) && fnRatio > 0 ? fnRatio : 1;
}

/** cost(t) = fp_cost·FP + fn_cost·FN with fp_cost = 1 (per the payload cost model). */
export function rowCost(row: ConfusionRow | undefined | null, fnRatio: number): number {
  const r = safeRow(row);
  return r.fp + safeRatio(fnRatio) * r.fn;
}

/** Campaign cost at the cursor threshold, under the given miss multiplier. */
export function costAt(row: ConfusionRow | undefined | null, fnRatio: number): number {
  return rowCost(row, fnRatio);
}

/** FP-cost component across the threshold grid (fp_cost = 1 per the cost model). */
export function fpCostSeries(overall: ConfusionRow[]): number[] {
  return (overall ?? []).map((r) => safeRow(r).fp);
}

/** FN-cost component across the threshold grid, scaled by the miss multiplier. */
export function fnCostSeries(overall: ConfusionRow[], fnRatio: number): number[] {
  return (overall ?? []).map((r) => safeRatio(fnRatio) * safeRow(r).fn);
}

/** Cost delta vs the default 0.5 threshold (negative = savings). */
export function savings(
  row: ConfusionRow | undefined | null,
  defaultRow: ConfusionRow | undefined | null,
  fnRatio: number,
): number {
  return rowCost(row, fnRatio) - rowCost(defaultRow, fnRatio);
}

/** How many holdout customers get contacted at the cursor threshold. */
export function contactCount(row: ConfusionRow | undefined | null): number {
  const r = safeRow(row);
  return r.fp + r.tp;
}

/** Fraction of churners the campaign catches at the cursor threshold. */
export function recallAt(row: ConfusionRow | undefined | null): number {
  const r = safeRow(row);
  const churners = r.tp + r.fn;
  return churners === 0 ? 0 : r.tp / churners;
}

/** Index of the threshold grid value nearest to t. */
export function nearestIndex(thresholds: number[], t: number): number {
  if (!Array.isArray(thresholds) || thresholds.length === 0) return 0;
  let best = 0;
  for (let i = 1; i < thresholds.length; i++) {
    if (Math.abs(thresholds[i] - t) < Math.abs(thresholds[best] - t)) best = i;
  }
  return best;
}
