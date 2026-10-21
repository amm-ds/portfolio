import type { ConfusionRow } from "../types";

/** cost(t) = fp_cost·FP + fn_cost·FN with fp_cost = 1 (per the payload cost model). */
export function rowCost(row: ConfusionRow, fnRatio: number): number {
  return row.fp + fnRatio * row.fn;
}

/** Campaign cost at the cursor threshold, under the given miss multiplier. */
export function costAt(row: ConfusionRow, fnRatio: number): number {
  return rowCost(row, fnRatio);
}

/** FP-cost component across the threshold grid (fp_cost = 1 per the cost model). */
export function fpCostSeries(overall: ConfusionRow[]): number[] {
  return overall.map((r) => r.fp);
}

/** FN-cost component across the threshold grid, scaled by the miss multiplier. */
export function fnCostSeries(overall: ConfusionRow[], fnRatio: number): number[] {
  return overall.map((r) => fnRatio * r.fn);
}

/** Cost delta vs the default 0.5 threshold (negative = savings). */
export function savings(row: ConfusionRow, defaultRow: ConfusionRow, fnRatio: number): number {
  return rowCost(row, fnRatio) - rowCost(defaultRow, fnRatio);
}

/** How many holdout customers get contacted at the cursor threshold. */
export function contactCount(row: ConfusionRow): number {
  return row.fp + row.tp;
}

/** Fraction of churners the campaign catches at the cursor threshold. */
export function recallAt(row: ConfusionRow): number {
  const churners = row.tp + row.fn;
  return churners === 0 ? 0 : row.tp / churners;
}

/** Index of the threshold grid value nearest to t. */
export function nearestIndex(thresholds: number[], t: number): number {
  let best = 0;
  for (let i = 1; i < thresholds.length; i++) {
    if (Math.abs(thresholds[i] - t) < Math.abs(thresholds[best] - t)) best = i;
  }
  return best;
}

/**
 * One-sentence, state-aware takeaway for the workbench Notice: what catching
 * one more churner costs at the cursor, given the current miss multiplier.
 * `laxer` is the confusion row one step toward contacting more customers
 * (lower threshold); when it catches no extra churners the sentence switches
 * to the recall ceiling.
 */
export function noticeText(
  cursorRow: ConfusionRow,
  laxer: ConfusionRow | null,
  fnRatio: number,
): string {
  if (laxer && laxer.tp > cursorRow.tp) {
    const gained = laxer.tp - cursorRow.tp;
    const extraAlarms = Math.max(laxer.fp + laxer.tp - (cursorRow.fp + cursorRow.tp), 0);
    const per = extraAlarms / gained;
    const rounded = per >= 10 ? Math.round(per) : Math.round(per * 10) / 10;
    return `at ${fnRatio}× a miss, catching one more churner here costs ~${rounded} extra false alarms`;
  }
  const recall = Math.round(recallAt(cursorRow) * 100);
  return `at ${fnRatio}× a miss this threshold already catches ${recall}% of churners — every additional alarm is a false one`;
}
